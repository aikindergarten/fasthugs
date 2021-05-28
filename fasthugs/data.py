# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/00_data.ipynb (unless otherwise specified).

__all__ = ['get_splits', 'TextGetter', 'find_first', 'split_by_sep', 'TokTransform', 'TokBatchTransform',
           'PadBatchTransform', 'untuple', 'to_tuple', 'LMBatchTfm', 'Undict', 'UndictS2S', 'TransformersTextBlock',
           'TransformersLMBlock', 'tokenize', 'group_texts']

# Cell
from fastcore.all import *
from fastai.basics import Transform, ItemTransform
from fastai.text.all import *
from functools import partial
from transformers import (AutoTokenizer, AutoConfig, BatchEncoding,
                          DataCollatorForLanguageModeling,
                          DataCollatorForWholeWordMask)

# Cell
def get_splits(dataset, train='train', valid='validation'):
    nt, nv = len(dataset[train]), len(dataset[valid])
    return L(range(nt)), L(range(nt, nt+nv))

# def DatasetSplitter(train='train', valid='validation'):
#     return partial(get_splits, train=train, valid=valid)

# Cell
class TextGetter(ItemTransform):
    def __init__(self, s1='text', s2=None):
        self.s1, self.s2 = s1, s2
    def encodes(self, sample):
        if self.s2 is None: return sample[self.s1]
        else: return sample[self.s1], sample[self.s2]

# Cell
@typedispatch
def show_batch(x:TensorText, y, samples, ctxs=None, max_n=10, trunc_at=150, **kwargs):
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
                 pre_tokenized=False, **kwargs):
        if tokenizer is None:
            tokenizer = tokenizer_cls.from_pretrained(pretrained_model_name, config=config)
        self.tokenizer = tokenizer
        self.kwargs = kwargs
        store_attr()

    def encodes(self, x):
        if self.pre_tokenized:
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

    def decodes(self, x:TensorText):
        return TitledStr(self.tokenizer.decode(x.cpu(), skip_special_tokens=False))

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
                 do_targets=False, **kwargs):
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
                targets = self.tokenizer(target_texts,
                                  padding=self.padding,
                                  truncation=self.truncation,
                                  max_length=self.max_length,
                                  return_tensors='pt',
                                  **self.kwargs).input_ids
            inps['labels'] = targets
            res = (inps, )
        else:
            # inps are batched, collate targets into batches too
            labels = default_collate([s[1:] for s in batch])
            if self.with_labels:
                # TODO consider cases when there are multiple labels
                inps['labels'] = labels[0]
                res = (inps, )
            else:
                res = (inps, ) + tuple(labels)
        return res

    def decodes(self, x:TensorText):
        if self._two_texts:
            x1, x2 = split_by_sep(x, self.tokenizer.sep_token_id)
            return (TitledStr(self.tokenizer.decode(x1.cpu(), skip_special_tokens=True)),
                    TitledStr(self.tokenizer.decode(x2.cpu(), skip_special_tokens=True)))
        return TitledStr(self.tokenizer.decode(x.cpu(), skip_special_tokens=True))

# Cell
class PadBatchTransform(Transform):
    def __init__(self, pretrained_model_name=None, tokenizer_cls=AutoTokenizer,
                 config=None, tokenizer=None, is_lm=False, with_labels=False,
                 padding=True, truncation=True, max_length=None,
                 do_targets=False, **kwargs):
        if tokenizer is None:
            tokenizer = tokenizer_cls.from_pretrained(pretrained_model_name, config=config)
        self.tokenizer = tokenizer
        self.kwargs = kwargs
        self._two_texts = False
        store_attr()

    def encodes(self, samples):
        toks = [s[0] for s in samples]
        inps = self.tokenizer.pad(toks,
                              padding=self.padding,
                              max_length=self.max_length,
                              return_tensors='pt',
                              **self.kwargs)

        # inps are batched, collate targets into batches too
        labels = default_collate([s[1:] for s in samples])

        res = (inps, ) + tuple(labels)
        return res

    def decodes(self, x:TensorText):
        if self._two_texts:
            x1, x2 = split_by_sep(x, self.tokenizer.sep_token_id)
            return (TitledStr(self.tokenizer.decode(x1.cpu(), skip_special_tokens=True)),
                    TitledStr(self.tokenizer.decode(x2.cpu(), skip_special_tokens=True)))
        return TitledStr(self.tokenizer.decode(x.cpu(), skip_special_tokens=True))

# Cell
def untuple(l):
    return [e[0] for e in l]

def to_tuple(x):
    return (x, )

# Cell
class LMBatchTfm(Transform):
    "Collates batch of pretokenized and chunked inputs into a batch and creates labels as defined by `masking_func`"
    def __init__(self, pretrained_model_name=None, tokenizer_cls=AutoTokenizer,
                 config=None, tokenizer=None, mlm=True, masking_func=None, whole_word_masking=False, mlm_probability=0.15):
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
        if 'input_ids' in b: res = TensorText(b['input_ids'])
        return res

# Cell
class Undict(ItemTransform):

    def decodes(self, b):
        # this is done hacky way to make show_batch work both when labels are separate and when in dict
        # should be a better way
        x = b[0]
        if 'input_ids' in x: res = (TensorText(x['input_ids']), )
        if 'labels' in x: res += (x['labels'], )
        return res + tuple(b[1:])

# Cell
class UndictS2S(ItemTransform):

    def decodes(self, b):
        x = b[0]
        if 'input_ids' in x: res = (TensorText(x['input_ids']), )
        if 'labels' in x: res += (TensorText(x['labels']), )
        return res + tuple(b[1:])

# Cell
class TransformersTextBlock(TransformBlock):
    "A `TransformBlock` for texts using pretrained tokenizers from Huggingface"
    @delegates(TokBatchTransform)
    def __init__(self, pretrained_model_name=None, tokenizer_cls=AutoTokenizer,
                 config=None, tokenizer=None, preprocessed=False, do_targets=False,
                 **kwargs):
        batch_tfm_cls = PadBatchTransform if preprocessed else TokBatchTransform
        before_batch_tfm = batch_tfm_cls(pretrained_model_name=pretrained_model_name, tokenizer_cls=tokenizer_cls,
                 config=config, tokenizer=tokenizer, do_targets=do_targets, **kwargs)
        return super().__init__(dl_type=SortedDL,
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
                 mlm_probability=0.15, **kwargs):
        tok_tfm = TokTransform(pretrained_model_name=pretrained_model_name, tokenizer_cls=tokenizer_cls,
                 config=config, tokenizer=tokenizer, return_special_tokens_mask=True, is_lm=True, **kwargs)

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