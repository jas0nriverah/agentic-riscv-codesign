# Preserved strict replay failure

The original prelabel runtime remains unchanged. Its final comparison includes host `mean_inference_seconds` in endpoint rows, although its existing exact policy replay correctly excludes nondeterministic host inference time. Raw processor authentication, live decision recreation and all15 grouped model refit checks precede this final error.

The explicit post-collection replay adapter must compare every other endpoint field exactly and retain both old/new inference timings. Candidate costs, clocks, model predictions and query decisions are never adjusted. No native measurements are repeated.
