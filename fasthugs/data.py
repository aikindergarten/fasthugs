# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/00_data.ipynb (unless otherwise specified).

__all__ = ['get_splits', 'TitledStrEx', 'TextGetter', 'KeyGetter', 'TransTensorText', 'find_first', 'split_by_sep',
           'TokTransform', 'TokBatchTransform', 'PadBatchTransform', 'untuple', 'to_tuple', 'LMBatchTfm', 'Undict',
           'UndictS2S', 'TransformersTextBlock', 'TransformersLMBlock', 'tokenize', 'group_texts',
           'MultiChoiceTransform', 'MultiChoiceBlock']

# Cell
from fastcore.all import *
from fastai.basics import Transform, ItemTransform
from fastai.text.all import *
from functools import partial
from collections import UserString
from transformers import (AutoTokenizer, AutoConfig, BatchEncoding,
                          DataCollatorForLanguageModeling,
                          DataCollatorForWholeWordMask)

from typing import Iterable

# Cell
def get_splits(dataset, train='train', valid='validation'):
    nt, nv = len(dataset[train]), len(dataset[valid])
    return L(range(nt)), L(range(nt, nt+nv))

# def DatasetSplitter(train='train', valid='validation'):
#     return partial(get_splits, train=train, valid=valid)

# Cell
class TitledStrEx(UserString):
    "TitledStr with option to set label"
    _show_args = {'label':'text'}
    def __init__(self, *args, **kwargs):
        label = kwargs.pop('label', None)
        if label is not None:
            self._show_args = {'label':label}
        super().__init__(*args, **kwargs)
    @property
    def label(self):
        return self._show_args['label']
    def truncate(self, n):
        "Truncate self to `n`"
        words = self.split(' ')[:n]
        return TitledStrEx(' '.join(words), label=self.label)
    def show(self, ctx=None, **kwargs):
        "Show self"
        return show_title(str(self), ctx=ctx, **merge(self._show_args, kwargs))

# Cell
class TextGetter(ItemTransform):
    "Retrieves text fields `s1` and [optionally] `s2`. Adds corresponding prefixes"
    def __init__(self, s1:str='text', s2:str=None, prefix1:str='', prefix2:str=''):
        store_attr()

    def encodes(self, sample):
        if self.s2 is None: return self.prefix1 + sample[self.s1]
        else: return self.prefix1+sample[self.s1], self.prefix2+sample[self.s2]

# Cell
class KeyGetter(ItemTransform):
    "Returns a dict with `keys` retrieved from input sample"
    def __init__(self, keys:Iterable):
        self.keys = set(keys)

    def encodes(self, sample):
        # TODO warn when key is not in sample.keys()
        return {k:v for k,v in sample.items() if k in self.keys}

# Cell
class TransTensorText(TensorText): pass

# Cell
@typedispatch
def show_batch(x:TransTensorText, y, samples, ctxs=None, max_n=10, trunc_at=150, **kwargs):
    if ctxs is None: ctxs = get_empty_df(min(len(samples), max_n))
    if isinstance(samples[0][0], tuple):
        samples = L((*s[0], *s[1:]) for s in samples)
        if trunc_at is not None: samples = L((s[0].truncate(trunc_at), s[1].truncate(trunc_at), *s[2:]) for s in samples)
    if trunc_at is not None: samples = L((s[0].truncate(trunc_at),*s[1:]) for s in samples)
    ctxs = show_batch[object](x, y, samples, max_n=max_n, ctxs=ctxs, **kwargs)
    display_df(pd.DataFrame(ctxs))

# Cell
def find_first(t, e):
    for i, v in enumerate(t):
        if v == e: return i

def split_by_sep(t, sep_tok_id):
    idx = find_first(t, sep_tok_id)
    return t[:idx], t[idx:]

# Cell
class TokTransform(Transform):
    "Tokenizes single piece of text using pretrained tokenizer"
    def __init__(self, pretrained_model_name=None, tokenizer_cls=AutoTokenizer,
                 config=None, tokenizer=None, is_lm=False,
                 padding=False, truncation=False, max_length=None,
                 preprocessed=False, **kwargs):
        if tokenizer is None:
            tokenizer = tokenizer_cls.from_pretrained(pretrained_model_name, config=config)
        self.tokenizer = tokenizer
        self.kwargs = kwargs
        store_attr()

    def encodes(self, x):
        if self.preprocessed:
            toks = x
        else:
            toks = self.tokenizer(x,
                          add_special_tokens=True,
                          padding=self.padding,
                          truncation=self.truncation,
                          max_length=self.max_length,
                          return_tensors='pt',
                          **self.kwargs)
        return toks

    def decodes(self, x:TransTensorText):
        return TitledStrEx(self.tokenizer.decode(x.cpu(), skip_special_tokens=False))

# Cell
class TokBatchTransform(Transform):
    """
    Tokenizes texts in batches using pretrained HuggingFace tokenizer.
    The first element in a batch can be single string or 2-tuple of strings.
    If `with_labels=True` the "labels" are added to the output dictionary.
    """
    def __init__(self, pretrained_model_name=None, tokenizer_cls=AutoTokenizer,
                 config=None, tokenizer=None, is_lm=False, with_labels=False,
                 padding=True, truncation=True, max_length=None,
                 do_targets=False, target_pad_id=-100, **kwargs):
        if tokenizer is None:
            tokenizer = tokenizer_cls.from_pretrained(pretrained_model_name, config=config)
        self.tokenizer = tokenizer
        self.kwargs = kwargs
        self._two_texts = False
        store_attr()

    def encodes(self, batch):
        # batch is a list of tuples of ({text or (text1, text2)}, {targets...})
        if is_listy(batch[0][0]): # 1st element is tuple
            self._two_texts = True
            texts = ([s[0][0] for s in batch], [s[0][1] for s in batch])
        elif is_listy(batch[0]):
            texts = ([s[0] for s in batch],)
        else: # batch is list of texts
            texts = (list(batch),)
            batch = [(s, ) for s in batch]
        inps = self.tokenizer(*texts,
                              add_special_tokens=True,
                              padding=self.padding,
                              truncation=self.truncation,
                              max_length=self.max_length,
                              return_tensors='pt',
                              **self.kwargs)

        if self.do_targets and isinstance(batch[0][1], str):
            target_texts = [s[1] for s in batch]
            with self.tokenizer.as_target_tokenizer():
                target_enc = self.tokenizer(target_texts,
                                  padding=self.padding,
                                  truncation=self.truncation,
                                  max_length=self.max_length,
                                  return_tensors='pt',
                                  **self.kwargs)
            targets = target_enc.input_ids
            if self.target_pad_id != self.tokenizer.pad_token_id:
                tgt_attn_mask = target_enc.attention_mask.to(torch.bool)
                targets = torch.where(tgt_attn_mask, targets, -100)
            targets = (TransTensorText(targets), )
        else:
            # inps are batched, collate targets into batches too
            targets = default_collate([s[1:] for s in batch])
        if self.with_labels:
            # TODO consider cases when there are multiple labels
            inps['labels'] = targets[0]
            res = (inps, )
        else:
            res = (inps, ) + tuple(targets)
        return res

    def decodes(self, x:TransTensorText):
        if self._two_texts:
            x1, x2 = split_by_sep(x, self.tokenizer.sep_token_id)
            return (TitledStrEx(self.tokenizer.decode(x1.cpu(), skip_special_tokens=True)),
                    TitledStrEx(self.tokenizer.decode(x2.cpu(), skip_special_tokens=True)))
        if self.do_targets:
            x = torch.where(x == -100, self.tokenizer.pad_token_id, x)
        return TitledStrEx(self.tokenizer.decode(x.cpu(), skip_special_tokens=True))

# Cell
class PadBatchTransform(Transform):
    def __init__(self, pretrained_model_name=None, tokenizer_cls=AutoTokenizer,
                 config=None, tokenizer=None, is_lm=False, with_labels=False,
                 padding=True, truncation=True, max_length=None,
                 do_targets=False, target_pad_id=-100, **kwargs):
        if tokenizer is None:
            tokenizer = tokenizer_cls.from_pretrained(pretrained_model_name, config=config)
        self.tokenizer = tokenizer
        self.kwargs = kwargs
        self._two_texts = False
        store_attr()

    def encodes(self, samples):
        toks = [s[0] for s in samples]
        if self.do_targets and ('labels' in toks[0].keys()):
            label_lens = [len(s['labels']) for s in toks]
            max_label_length = max(label_lens)
            padding_side = self.tokenizer.padding_side
            for tok, label_len in zip(toks, label_lens):
                remainder = [self.target_pad_id] * (max_label_length - label_len)
                tok["labels"] = (tok["labels"] + remainder
                                 if padding_side=="right" else
                                 remainder + tok["labels"])
        inps = self.tokenizer.pad(toks,
                              padding=self.padding,
                              max_length=self.max_length,
                              return_tensors='pt',
                              **self.kwargs)
        inps = {k:TransTensorText(v) for k, v in inps.items() if (isinstance(v, torch.Tensor) and v.dim()>1)}
        # inps are batched, collate targets into batches too
        labels = default_collate([s[1:] for s in samples])
        res = (inps, ) + tuple(labels)
        return res

    def decodes(self, x:TransTensorText):
        if self._two_texts:
            x1, x2 = split_by_sep(x, self.tokenizer.sep_token_id)
            return (TitledStrEx(self.tokenizer.decode(x1.cpu(), skip_special_tokens=True)),
                    TitledStrEx(self.tokenizer.decode(x2.cpu(), skip_special_tokens=True)))
        if self.do_targets:
            x = torch.where(x == -100, self.tokenizer.pad_token_id, x)
        return TitledStrEx(self.tokenizer.decode(x.cpu(), skip_special_tokens=True))

# Cell
def untuple(l):
    return [e[0] for e in l]

def to_tuple(x):
    return (x, )

# Cell
class LMBatchTfm(Transform):
    "Collates batch of pretokenized and chunked inputs into a batch and creates labels as defined by `masking_func`"
    def __init__(self, pretrained_model_name=None, tokenizer_cls=AutoTokenizer,
                 config=None, tokenizer=None, mlm=True, masking_func=None, whole_word_masking=False,
                 mlm_probability=0.15):
        if tokenizer is None:
            tokenizer = tokenizer_cls.from_pretrained(pretrained_model_name, config=config)
        if masking_func is None:
            masking_func = (DataCollatorForWholeWordMask(tokenizer, mlm, mlm_probability)
                            if whole_word_masking else
                            DataCollatorForLanguageModeling(tokenizer, mlm, mlm_probability))
        self.masking_func = masking_func
        self.batch_processor = compose(untuple, masking_func, to_tuple)

    def encodes(self, b):
        # we get list of tuples but need a list of dicts
        return self.batch_processor(b)

    def decodes(self, b:(dict, BatchEncoding)):
        if 'input_ids' in b: res = TransTensorText(b['input_ids'])
        return res

# Cell
class Undict(ItemTransform):

    def decodes(self, b):
        # this is done hacky way to make show_batch work both when labels are separate and when in dict
        # should be a better way
        x = b[0]
        if 'input_ids' in x: res = (TransTensorText(x['input_ids']), )
        if 'labels' in x: res += (x['labels'], )
        return res + tuple(b[1:])

# Cell
class UndictS2S(ItemTransform):

    def decodes(self, b):
        x = b[0]
        if 'input_ids' in x: res = (TransTensorText(x['input_ids']), )
        if 'labels' in x: res += (TransTensorText(x['labels']), )
        return res + tuple(b[1:])

# Cell
class TransformersTextBlock(TransformBlock):
    "A `TransformBlock` for texts using pretrained tokenizers from Huggingface"
    @delegates(TokBatchTransform)
    def __init__(self, pretrained_model_name=None, tokenizer_cls=AutoTokenizer,
                 config=None, tokenizer=None, preprocessed=False, do_targets=False,
                 group_by_len=True, **kwargs):
        batch_tfm_cls = PadBatchTransform if preprocessed else TokBatchTransform
        before_batch_tfm = batch_tfm_cls(pretrained_model_name=pretrained_model_name, tokenizer_cls=tokenizer_cls,
                 config=config, tokenizer=tokenizer, do_targets=do_targets, **kwargs)
        return super().__init__(dl_type=SortedDL if group_by_len else TfmdDL,
                                dls_kwargs={'before_batch': before_batch_tfm,
                                            'create_batch': fa_convert},
                                batch_tfms=UndictS2S() if do_targets else Undict()
                               )

#     @classmethod
#     def from_pretrained(cls, ):
#         pass

#     @classmethod
#     def from_tokenizer(cls, ):
#         pass

#     @classmethod
#     def from_config(cls, ):
#         pass

# Cell
class TransformersLMBlock(TransformBlock):
    "A `TransformBlock` for texts using pretrained tokenizers from Huggingface"
    # @delegates
    def __init__(self, pretrained_model_name=None, tokenizer_cls=AutoTokenizer,
                 config=None, tokenizer=None, mlm=True, masking_func=None, whole_word_masking=False,
                 mlm_probability=0.15, preprocessed=True, **kwargs):
        tok_tfm = TokTransform(pretrained_model_name=pretrained_model_name, tokenizer_cls=tokenizer_cls,
                     config=config, tokenizer=tokenizer, return_special_tokens_mask=True, is_lm=True,
                     preprocessed=preprocessed, **kwargs)

        batch_tfms = LMBatchTfm(pretrained_model_name, tokenizer_cls, config, tokenizer,
                                mlm=mlm, masking_func=masking_func, whole_word_masking=whole_word_masking,
                                mlm_probability=mlm_probability)
        create_batch = compose(untuple, DataCollatorForLanguageModeling(tokenizer), to_tuple)
        return super().__init__(dl_type=TfmdDL,
                                type_tfms=tok_tfm,
                                batch_tfms=batch_tfms,
                                dls_kwargs={'create_batch': fa_convert},
                               )

# Cell
def tokenize(batch):
    return tokenizer(batch['text'], return_attention_mask=True, return_special_tokens_mask=True, verbose=False)

def group_texts(examples):
    # Concatenate all texts.
    concatenated_examples = {k: sum(examples[k], []) for k in examples.keys()}
    total_length = len(concatenated_examples[list(examples.keys())[0]])
    # We drop the small remainder, we could add padding if the model supported it instead of this drop, you can
        # customize this part to your needs.
    total_length = (total_length // block_size) * block_size
    # Split by chunks of max_len.
    result = {
        k: [t[i : i + block_size] for i in range(0, total_length, block_size)]
        for k, t in concatenated_examples.items()
    }
    return result

# Cell
class MultiChoiceTransform(Transform):
    """
    Processes inputs for multiple choice
    """
    def __init__(self, sentence_keys, ending_keys,
                 pretrained_model_name=None, tokenizer_cls=AutoTokenizer,
                 config=None, tokenizer=None, with_labels=False, padding=True,
                 truncation=True, max_length=None, **kwargs):
        if tokenizer is None:
            tokenizer = tokenizer_cls.from_pretrained(pretrained_model_name, config=config)
        self.tokenizer = tokenizer
        self.kwargs = kwargs
        store_attr()

    def encodes(self, batch):
        # inputs are list of tuple(dict, label)
        inps = [b[0] for b in batch]
        sk1, sk2 = self.sentence_keys
        num_endings = len(self.ending_keys)
        texts1, texts2 = [], []
        for s in inps:
            texts1.extend([s[sk1]]*num_endings)
            texts2.extend([f"{s[sk2]} {s[e]}" for e in self.ending_keys])
        inps = self.tokenizer(texts1, texts2,
                              add_special_tokens=True,
                              padding=self.padding,
                              truncation=self.truncation,
                              max_length=self.max_length,
                              return_tensors='pt',
                              **self.kwargs)
        inps = {k:v.reshape(-1, num_endings, v.size(1)) for k,v in inps.items()}

        targets = default_collate([s[1:] for s in batch])
        if self.with_labels:
            inps['labels'] = targets[0]
            res = (inps, )
        else:
            res = (inps, ) + tuple(targets)
        return res

    def decodes(self, x:TransTensorText):
        endings = ()
        for i, l in enumerate(self.ending_keys):
            x1, x2 = split_by_sep(x[i, :], self.tokenizer.sep_token_id)
            endings += (TitledStrEx(self.tokenizer.decode(x2.cpu(), skip_special_tokens=True), label=l),)
        return (TitledStrEx(self.tokenizer.decode(x1.cpu(), skip_special_tokens=True), label=self.sentence_keys[0]), ) + endings

# Cell
class MultiChoiceBlock(TransformBlock):
    "A `TransformBlock` for texts using pretrained tokenizers from Huggingface"
    @delegates(MultiChoiceTransform)
    def __init__(self, sentence_keys, ending_keys, pretrained_model_name=None, tokenizer_cls=AutoTokenizer,
                 config=None, tokenizer=None, preprocessed=False, group_by_len=True,
                 **kwargs):
        batch_tfm_cls = MultiChoiceTransform
        before_batch_tfm = batch_tfm_cls(sentence_keys, ending_keys, pretrained_model_name=pretrained_model_name,
                tokenizer_cls=tokenizer_cls, config=config, tokenizer=tokenizer, **kwargs)
        return super().__init__(dl_type=SortedDL if group_by_len else TfmdDL,
                                dls_kwargs={'before_batch': before_batch_tfm,
                                            'create_batch': fa_convert},
                                batch_tfms=Undict())