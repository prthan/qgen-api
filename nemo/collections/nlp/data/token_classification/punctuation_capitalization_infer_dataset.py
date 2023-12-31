# Copyright (c) 2021, NVIDIA CORPORATION & AFFILIATES.  All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import itertools
from typing import Dict, List, Optional, Tuple

import numpy as np
import torch
from torch.nn.utils.rnn import pad_sequence

from nemo.collections.common.tokenizers.tokenizer_spec import TokenizerSpec
from nemo.collections.nlp.data.data_utils.data_preprocessing import get_stats
from nemo.core.classes.dataset import Dataset
from nemo.core.neural_types.elements import ChannelType, Index, MaskType
from nemo.core.neural_types.neural_type import NeuralType
from nemo.core.neural_types.elements import BoolType
from nemo.utils import logging


def get_features_infer(
    queries: List[str],
    tokenizer: TokenizerSpec,
    max_seq_length: int = 64,
    step: Optional[int] = 8,
    margin: Optional[int] = 16,
) -> Tuple[
    List[List[int]], List[List[int]], List[List[int]], List[List[int]], List[int], List[int], List[bool], List[bool],
]:
    """
    Processes the data and returns features.

    Args:
        queries: text sequences
        tokenizer: such as AutoTokenizer
        max_seq_length: max sequence length minus 2 for [CLS] and [SEP]
        step: relative shift of consequent segments into which long queries are split. Long queries are split into
            segments which can overlap. Parameter ``step`` controls such overlapping. Imagine that queries are
            tokenized into characters, ``max_seq_length=5``, and ``step=2``. In such a case query "hello" is
            tokenized into segments ``[['[CLS]', 'h', 'e', 'l', '[SEP]'], ['[CLS]', 'l', 'l', 'o', '[SEP]']]``.
        margin: number of subtokens near edges of segments which are not used for punctuation and capitalization
            prediction. The first segment does not have left margin and the last segment does not have right
            margin. For example, if input sequence is tokenized into characters, ``max_seq_length=5``,
            ``step=1``, and ``margin=1``, then query "hello" will be tokenized into segments
            ``[['[CLS]', 'h', 'e', 'l', '[SEP]'], ['[CLS]', 'e', 'l', 'l', '[SEP]'],
            ['[CLS]', 'l', 'l', 'o', '[SEP]']]``. These segments are passed to the model. Before final predictions
            computation, margins are removed. In the next list, subtokens which logits are not used for final
            predictions computation are marked with asterisk: ``[['[CLS]'*, 'h', 'e', 'l'*, '[SEP]'*],
            ['[CLS]'*, 'e'*, 'l', 'l'*, '[SEP]'*], ['[CLS]'*, 'l'*, 'l', 'o', '[SEP]'*]]``.

    Returns:
        all_input_ids: list of input ids of all segments
        all_segment_ids: token type ids of all segments
        all_input_mask: attention mask to use for BERT model
        all_subtokens_mask: masks out all subwords besides the first one
        all_quantities_of_preceding_words: number of words in query preceding a segment. Used for joining
            predictions from overlapping segments.
        all_query_ids: index of a query to which segment belongs
        all_is_first: is segment first segment in a query
        all_is_last: is segment last segment in a query
    """
    st = []
    stm = []
    sent_lengths = []
    for i, query in enumerate(queries):
        subtokens, subtokens_mask = _get_subtokens_and_subtokens_mask(query, tokenizer)
        sent_lengths.append(len(subtokens))
        st.append(subtokens)
        stm.append(subtokens_mask)
    _check_max_seq_length_and_margin_and_step(max_seq_length, margin, step)
    if max_seq_length > max(sent_lengths) + 2:
        max_seq_length = max(sent_lengths) + 2
        # If `max_seq_length` is greater than maximum length of input query, parameters ``margin`` and ``step`` are
        # not used will not be used.
        step = 1
        # Maximum number of word subtokens in segment. The first and the last tokens in segment are CLS and EOS
        length = max_seq_length - 2
    else:
        # Maximum number of word subtokens in segment. The first and the last tokens in segment are CLS and EOS
        length = max_seq_length - 2
        step = min(length - margin * 2, step)
    logging.info(f'Max length: {max_seq_length}')
    get_stats(sent_lengths)
    all_input_ids, all_segment_ids, all_subtokens_mask, all_input_mask, all_input_mask = [], [], [], [], []
    all_quantities_of_preceding_words, all_query_ids, all_is_first, all_is_last = [], [], [], []
    for q_i, query_st in enumerate(st):
        q_inp_ids, q_segment_ids, q_subtokens_mask, q_inp_mask, q_quantities_of_preceding_words = [], [], [], [], []
        for i in range(0, max(len(query_st), length) - length + step, step):
            subtokens = [tokenizer.cls_token] + query_st[i : i + length] + [tokenizer.sep_token]
            q_inp_ids.append(tokenizer.tokens_to_ids(subtokens))
            q_segment_ids.append([0] * len(subtokens))
            q_subtokens_mask.append([False] + stm[q_i][i : i + length] + [False])
            q_inp_mask.append([True] * len(subtokens))
            q_quantities_of_preceding_words.append(np.count_nonzero(stm[q_i][:i]))
        all_input_ids.append(q_inp_ids)
        all_segment_ids.append(q_segment_ids)
        all_subtokens_mask.append(q_subtokens_mask)
        all_input_mask.append(q_inp_mask)
        all_quantities_of_preceding_words.append(q_quantities_of_preceding_words)
        all_query_ids.append([q_i] * len(q_inp_ids))
        all_is_first.append([True] + [False] * (len(q_inp_ids) - 1))
        all_is_last.append([False] * (len(q_inp_ids) - 1) + [True])
    return (
        list(itertools.chain(*all_input_ids)),
        list(itertools.chain(*all_segment_ids)),
        list(itertools.chain(*all_input_mask)),
        list(itertools.chain(*all_subtokens_mask)),
        list(itertools.chain(*all_quantities_of_preceding_words)),
        list(itertools.chain(*all_query_ids)),
        list(itertools.chain(*all_is_first)),
        list(itertools.chain(*all_is_last)),
    )


def _check_max_seq_length_and_margin_and_step(max_seq_length: int, margin: int, step: int):
    """
    Checks values of ``max_seq_length``, ``margin``, and ``step``.
    Args:
        max_seq_length: a segment length with ``[CLS]`` and ``[SEP]`` tokens
        margin: a number of input tokens near edges of segments which are not used in punctuation and capitalization
            prediction.
        step: offset of consequent segments.
    Returns:
        None
    """
    if max_seq_length < 3:
        raise ValueError(
            f"Parameter `max_seq_length={max_seq_length}` cannot be less than 3 because `max_seq_length` is a length "
            f"of a segment with [CLS] and [SEP] tokens."
        )
    if margin >= (max_seq_length - 2) // 2 and margin > 0 or margin < 0:
        raise ValueError(
            f"Parameter `margin` has to be not negative and less than `(max_seq_length - 2) // 2`. Don't forget about "
            f"CLS and EOS tokens in the beginning and the end of segment. margin={margin}, "
            f"max_seq_length={max_seq_length}"
        )
    if step <= 0:
        raise ValueError(f"Parameter `step` has to be positive whereas step={step}")
    if step > max_seq_length - 2 - 2 * margin:
        logging.warning(
            f"Parameter step={step} is too big. It will be reduced to `min(max_seq_length, <maximum query length> + 2) "
            f"- 2 - 2 * margin`."
        )


def _get_subtokens_and_subtokens_mask(query: str, tokenizer: TokenizerSpec) -> Tuple[List[str], List[bool]]:
    """
    Tokenizes input query into subtokens and creates subtokens mask. Subtokens mask is an array of the same length as
    subtokens array and contains zeros and ones in which. If element of mask equals 1, then corresponding subtoken in
    subtokens array is first subtoken in some word
    Args:
        query: a string that will be tokenized
        tokenizer: an instance of tokenizer
    Returns:
        subtokens: list of subtokens
        subtokens_mask: list of ints
    """
    words = query.strip().split()
    subtokens = []
    subtokens_mask = []
    for j, word in enumerate(words):
        word_tokens = tokenizer.text_to_tokens(word)
        subtokens.extend(word_tokens)
        subtokens_mask.append(True)
        subtokens_mask.extend([False] * (len(word_tokens) - 1))
    return subtokens, subtokens_mask


class BertPunctuationCapitalizationInferDataset(Dataset):
    """
    Creates dataset to use during inference for punctuation and capitalization tasks with a pretrained model.
    For dataset to use during training with labels, see
    :class:`~nemo.collections.nlp.data.token_classification.punctuation_capitalization_dataset.BertPunctuationCapitalizationDataset`
    and
    :class:`~nemo.collections.nlp.data.token_classification.punctuation_capitalization_tarred_dataset.BertPunctuationCapitalizationTarredDataset`.

    Parameters ``max_seq_length``, ``step``, ``margin`` are for controlling the way queries are split into segments
    which then processed by the model. Parameter ``max_seq_length`` is a length of a segment after tokenization
    including special tokens [CLS] in the beginning and [SEP] in the end of a segment. Parameter ``step`` is shift
    between consequent segments. Parameter ``margin`` is used to exclude negative effect of subtokens near
    borders of segments which have only one side context.

    Args:
        queries (:obj:`List[str]`): list of sequences.
        tokenizer (:obj:`TokenizerSpec`): a tokenizer which was used for model training. It should have properties
            ``cls_id``, ``sep_id``, ``unk_id``, ``pad_id``.
        max_seq_length (:obj:`int`, `optional`, defaults to :obj:`128`): max sequence length which includes [CLS] and
            [SEP] tokens
        step (:obj:`int`, `optional`, defaults to :obj:`8`): relative shift of consequent segments into which long
            queries are split. Long queries are split into segments which can overlap. Parameter ``step`` controls such
            overlapping. Imagine that queries are tokenized into characters, ``max_seq_length=5``, and ``step=2``. In
            such a case query "hello" is tokenized into segments
            ``[['[CLS]', 'h', 'e', 'l', '[SEP]'], ['[CLS]', 'l', 'l', 'o', '[SEP]']]``.
        margin (:obj:`int`, `optional`, defaults to :obj:`16`): number of subtokens in the beginning and the end of
            segments which are not used for prediction computation. The first segment does not have left margin and the
            last segment does not have right margin. For example, if input sequence is tokenized into characters,
            ``max_seq_length=5``, ``step=1``, and ``margin=1``, then query "hello" will be tokenized into segments
            ``[['[CLS]', 'h', 'e', 'l', '[SEP]'], ['[CLS]', 'e', 'l', 'l', '[SEP]'],
            ['[CLS]', 'l', 'l', 'o', '[SEP]']]``. These segments are passed to the model. Before final predictions
            computation, margins are removed. In the next list, subtokens which logits are not used for final
            predictions computation are marked with asterisk: ``[['[CLS]'*, 'h', 'e', 'l'*, '[SEP]'*],
            ['[CLS]'*, 'e'*, 'l', 'l'*, '[SEP]'*], ['[CLS]'*, 'l'*, 'l', 'o', '[SEP]'*]]``.
    """

    @property
    def output_types(self) -> Optional[Dict[str, NeuralType]]:
        """Returns neural types of :meth:`collate_fn` output."""
        return {
            'input_ids': NeuralType(('B', 'T'), ChannelType()),
            'segment_ids': NeuralType(('B', 'T'), ChannelType()),
            'input_mask': NeuralType(('B', 'T'), MaskType()),
            'subtokens_mask': NeuralType(('B', 'T'), MaskType()),
            'quantities_of_preceding_words': NeuralType(('B',), Index()),
            'query_ids': NeuralType(('B',), Index()),
            'is_first': NeuralType(('B',), BoolType()),
            'is_last': NeuralType(('B',), BoolType()),
        }

    def __init__(
        self, queries: List[str], tokenizer: TokenizerSpec, max_seq_length: int = 64, step: int = 8, margin: int = 16
    ):
        features = get_features_infer(
            queries=queries, max_seq_length=max_seq_length, tokenizer=tokenizer, step=step, margin=margin
        )
        self.all_input_ids: List[List[int]] = features[0]
        self.all_segment_ids: List[List[int]] = features[1]
        self.all_input_mask: List[List[int]] = features[2]
        self.all_subtokens_mask: List[List[int]] = features[3]
        self.all_quantities_of_preceding_words: List[int] = features[4]
        self.all_query_ids: List[int] = features[5]
        self.all_is_first: List[bool] = features[6]
        self.all_is_last: List[bool] = features[7]

    def __len__(self) -> int:
        return len(self.all_input_ids)

    def collate_fn(
        self, batch: List[Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, int, int, bool, bool]]
    ) -> Tuple[
        torch.Tensor,
        torch.Tensor,
        torch.Tensor,
        torch.Tensor,
        Tuple[int, ...],
        Tuple[int, ...],
        Tuple[bool, ...],
        Tuple[bool, ...],
    ]:
        """
        Collates samples into batches.

        Args:
            batch (:obj:`List[tuple]`): a list of samples returned by :meth:`__getitem__` method.

        Returns:
            :obj:`Tuple[torch.Tensor (x4), Tuple[int, ...] (x2), Tuple[bool, ...] (x2)]`: a tuple containing 8
            elements:

              - ``input_ids`` (:obj:`torch.Tensor`): an integer tensor of shape ``[Batch, Time]`` containing encoded
                input text.
              - ``segment_ids`` (:obj:`torch.Tensor`): an integer tensor of shape ``[Batch, Time]`` filled with zeros.
              - ``input_mask`` (:obj:`torch.Tensor`): a boolean tensor of shape ``[Batch, Time]`` which elements are
                ``True`` if corresponding token is not a padding token.
              - ``subtokens_mask`` (:obj:`torch.Tensor`): a boolean tensor of shape ``[Batch, Time]`` which elements
                are ``True`` if corresponding tken is the first token in a word.
              - ``quantities_of_preceding_words`` (:obj:`Tuple[int, ...]`):  a tuple containing number of words in
                a query preceding current segment.
              - ``query_ids`` (:obj:`Tuple[int, ...]`): a tuple containing indices of queries to which segments belong.
              - ``is_first`` (:obj:`Tuple[bool, ...]`): a tuple booleans which elements are ``True`` if corresponding
                segment is the first segment in a query.
              - ``is_last`` (:obj:`Tuple[bool, ...]`): a tuple of booleans which elements are ``True`` if corresponding
                segment is the last segment in a query.
        """
        inp_ids, segment_ids, inp_mask, st_mask, n_preceding, query_ids, is_first, is_last = zip(*batch)
        return (
            pad_sequence([torch.tensor(x) for x in inp_ids], batch_first=True, padding_value=0),
            pad_sequence([torch.tensor(x) for x in segment_ids], batch_first=True, padding_value=0),
            pad_sequence([torch.tensor(x) for x in inp_mask], batch_first=True, padding_value=0),
            pad_sequence([torch.tensor(x) for x in st_mask], batch_first=True, padding_value=0),
            n_preceding,
            query_ids,
            is_first,
            is_last,
        )

    def __getitem__(self, idx: int) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, int, int, bool, bool]:
        """
        Returns batch used for punctuation and capitalization inference.

        Args:
            idx (:obj:`int`): a batch index

        Returns:
            :obj:`Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, int, int, bool, bool]`: a tuple containing:

                - ``input_ids`` (:obj:`np.ndarray`): an integer numpy array of shape ``[Time]``. Ids of word
                  subtokens encoded using tokenizer passed in constructor ``tokenizer`` parameter.
                - ``segment_ids`` (:obj:`np.ndarray`): an integer zeros numpy array of shape ``[Time]``. Indices
                  of segments for BERT model (token types in HuggingFace terminology).
                - ``input_mask`` (:obj:`np.ndarray`): a boolean numpy array of shape ``[Time]``. An element of
                  this array is ``True`` if corresponding token is not padding token.
                - ``subtokens_mask`` (:obj:`np.ndarray`): a boolean numpy array of shape ``[Time]``. An element
                  equals ``True`` if corresponding token is the first token in a word and ``False`` otherwise. For
                  example, if input query ``"language processing"`` is tokenized into
                  ``["[CLS]", "language", "process", "ing", "SEP"]``, then ``subtokens_mask`` will be
                  ``[False, True, True, False, False]``.
                - ``quantities_of_preceding_words`` (:obj:`int`): a number of words preceding current segment in the
                  query to which the segment belongs. This parameter is used for uniting predictions from adjacent
                  segments.
                - ``query_ids`` (:obj:`int`): an index of query to which the segment belongs
                - ``is_first`` (:obj:`bool`): whether a segment is the first segment in a query. The left margin of
                  the first segment in a query is not removed.
                - ``is_last`` (:obj:`bool`): whether a query is the last query in a query. The right margin of the last
                  segment in a query is not removed.
        """
        return (
            np.array(self.all_input_ids[idx]),
            np.array(self.all_segment_ids[idx]),
            np.array(self.all_input_mask[idx], dtype=np.float32),
            np.array(self.all_subtokens_mask[idx]),
            self.all_quantities_of_preceding_words[idx],
            self.all_query_ids[idx],
            self.all_is_first[idx],
            self.all_is_last[idx],
        )
