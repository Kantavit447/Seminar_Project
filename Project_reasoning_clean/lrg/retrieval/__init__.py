"""Load live retrieval dependencies only when a live retriever is requested."""


def init_retriever(model_name, dataset, k, strat_name):
    from .retrieval_init import init_retriever as init_live_retriever

    return init_live_retriever(
        model_name=model_name,
        dataset=dataset,
        k=k,
        strat_name=strat_name,
    )
