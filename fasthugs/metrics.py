# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/02_metrics.ipynb (unless otherwise specified).

__all__ = ['RougeScore']

# Cell
from fastcore.all import *
from fastai.basics import Transform, ItemTransform, Callback, ValueMetric
from functools import partial
from typing import List
from datasets import load_metric
try:
    import nltk
except: pass
from .learner import TransCallback

# Cell
def _get_score(obj, score_name, agg, measure):
    return getattr(getattr(obj.res[score_name], agg), measure)

# Cell
class RougeScore(Callback):
    """
    Computes ROUGE score using HF datasets metric. Adds `ValueMetric`
    for each score iin `scores`
    """
    order = TransCallback.order + 2
    run_train, run_valid = False, True
    def __init__(self, tokenizer, argmax:bool=True, agg:str='mid', measure:str='fmeasure',
                 scores:List[str]=['rouge1', 'rouge2', 'rougeL', 'rougeLsum']):
        nltk.download('punkt', quiet=True)
        self.metric = load_metric("rouge")
        store_attr()
        self._register_value_funcs()

    def before_fit(self): self.add_metrics()

    def after_pred(self):
        if self.predict_with_generate:
            preds = self.generated_tokens
        else:
            preds = self.pred.argmax(-1)
        labels = self.yb[0] if len(self.yb) else self.trans.labels[0]
        # decode preds and labels
        decoded_preds = self.tokenizer.batch_decode(preds, skip_special_tokens=True)
        # Replace -100 in the labels as we can't decode them.
        labels = torch.where(labels != -100, labels, self.tokenizer.pad_token_id)
        decoded_labels = self.tokenizer.batch_decode(labels, skip_special_tokens=True)
        # Rouge expects a newline after each sentence
        decoded_preds = ["\n".join(nltk.sent_tokenize(pred.strip())) for pred in decoded_preds]
        decoded_labels = ["\n".join(nltk.sent_tokenize(label.strip())) for label in decoded_labels]
        self.metric.add_batch(predictions=decoded_preds, references=decoded_labels)

    def after_validate(self):
        self.res = self.metric.compute()

    def _register_value_funcs(self):
        for score in self.scores:
            func = partial(_get_score, self, score, self.agg, self.measure)
            setattr(self, score, func)

    def add_metrics(self):
        learn_metrics = set([m.name for m in self.metrics])
        for score_name in self.scores:
            if not (score_name in learn_metrics):
                self.learn.metrics += [ValueMetric(getattr(self, score_name), score_name)]
