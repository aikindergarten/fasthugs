# FastHugs
> Training HuggingFace models using fastai


## Install

```
pip install git+git://github.com/aikindergarten/fasthugs.git
```

## How to use

### Pre-training

[Masked Language modeling](https://aikindergarten.github.io/fasthugs/examples.mlm-imdb.html)

### Fine-tuning

1. [Sentiment classification: IMDB](https://aikindergarten.github.io/fasthugs/examples.classification-imdb.html)
2. [GLUE benchmark](https://aikindergarten.github.io/fasthugs/examples.glue-benchmark.html)
3. [Machine Translation](https://aikindergarten.github.io/fasthugs/examples.machine-translation.html)

### Hyper-parameter search

[W&B sweeps](https://aikindergarten.github.io/fasthugs/examples.glue-benchmark-sweeps.html)

And more coming soon...

## Acknoledgements

This library is lightweight wrapper for this two awesome libraries: HuggingFace [transformers](https://github.com/huggingface/transformers/) and [fastai](https://github.com/fastai/fastai/) and is inspired by other work in same direction namely earlier [fasthugs](https://github.com/morganmcg1/fasthugs) by @morganmcg1 and [blurr](https://github.com/ohmeow/blurr) by @ohmeow.
