# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/01_learner.ipynb (unless otherwise specified).

__all__ = ['default_splitter', 'to_device', 'TransCallback', 'GeneratePreds', 'TransLearner']

# Cell
from fastai.basics import *
from fastai.text.all import TensorText
from inspect import signature
from collections import namedtuple
from .data import TransformersTextBlock

from transformers import (AutoTokenizer, AutoConfig, AutoModelForSequenceClassification, BatchEncoding,
                          PreTrainedModel)
from transformers.modeling_outputs import QuestionAnsweringModelOutput

# Cell
def default_splitter(model):
    groups = L(model.base_model.children()) + L(m for m in list(model.children())[1:] if params(m))
    return groups.map(params)

# Cell
@typedispatch
def show_results(x: TensorText, y, samples, outs, ctxs=None, max_n=10, trunc_at=150, **kwargs):
    if ctxs is None: ctxs = get_empty_df(min(len(samples), max_n))
    if isinstance(samples[0][0], tuple):
        samples = L((*s[0], *s[1:]) for s in samples)
        if trunc_at is not None: samples = L((s[0].truncate(trunc_at), s[1].truncate(trunc_at), *s[2:]) for s in samples)
    elif trunc_at is not None: samples = L((s[0].truncate(trunc_at),*s[1:]) for s in samples)
    ctxs = show_results[object](x, y, samples, outs, ctxs=ctxs, max_n=max_n, **kwargs)
    display_df(pd.DataFrame(ctxs))
    return ctxs

# Cell
def to_device(b, device=None):
    "Recursively put `b` on `device`. Handles `BatchEncoding`s"
    if defaults.use_cuda==False: device='cpu'
    elif device is None: device=default_device()
    def _inner(o):
        if isinstance(o,Tensor): return o.to(device, non_blocking=True)
        elif isinstance(o,BatchEncoding): return o.to(device)
        # elif hasattr(o, "to_device"): return o.to_device(device)
        else: return o
    return apply(_inner, b)

# Cell
class TransCallback(Callback):
    "Handles HuggingFace model inputs and outputs"
    def __init__(self, model):
        sig = signature(model.forward)
        ModelInputs = namedtuple('ModelInputs', sig.parameters.keys(), defaults=[v.default for v in sig.parameters.values()])
        self._model_inputs = ModelInputs

    def before_batch(self):
        self.learn.xb = self._model_inputs(**{k:v for k,v in self.xb[0].items() if k in self._model_inputs._fields})

    def after_pred(self):
        if 'loss' in self.pred:
            self.learn.loss_grad = self.pred.loss
            self.learn.loss = self.pred.loss.clone()
        if isinstance(self.pred, QuestionAnsweringModelOutput):
            self.learn.pred = (self.pred.start_logits, self.pred.end_logits)
        else: self.learn.pred = self.pred.logits

    def after_loss(self):
        if not (getattr(self.xb, 'labels', None) is None):
            self.learn.yb = (self.xb.labels, )

# Cell
class GeneratePreds(Callback):
    "Produces `generated_tokens` which can be used for metrics computation"
    order = TransCallback.order-1
    run_train, run_valid = False, True
    @delegates(PreTrainedModel.generate)
    def __init__(self, **kwargs):
        self.gen_kwargs = kwargs
    def before_fit(self):
        self.learn.predict_with_generate = True
    def before_batch(self):
        input_ids, attention_mask = self.xb[0]['input_ids'], self.xb[0]['attention_mask']
        self.learn.generated_tokens = self.model.generate(input_ids=input_ids, attention_mask=attention_mask, **self.gen_kwargs)

# Cell
@delegates(Learner.__init__)
class TransLearner(Learner):
    "Learner for training transformers from HuggingFace"
    def __init__(self, dls, model:PreTrainedModel, predict_with_generate:bool=False, **kwargs):
        splitter = kwargs.get('splitter', None)
        if splitter is None: kwargs['splitter'] = default_splitter
        super().__init__(dls, model, **kwargs)
        self.add_cb(TransCallback(model))
        self.predict_with_generate = predict_with_generate

# Cell
@patch
def _set_device(self:TransLearner, b):
    model_device = torch.device(torch.cuda.current_device()) if next(self.model.parameters()).is_cuda else torch.device('cpu')
    dls_device = getattr(self.dls, 'device', default_device())
    if model_device == dls_device: return to_device(b, dls_device)
    else: return to_device(b, model_device)