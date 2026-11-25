# Historical access-filter evaluation

The earlier access-filter test made 40 public-user requests and observed no restricted evidence in the responses. In 20 admin positive-control requests, restricted evidence was retrieved in 19.

This test used the former synthetic chunk-level access split. It predates the current document-level access labels and public-by-default ingestion behavior, so it is historical evidence only—not validation of the current restricted-document workflow or a security guarantee.

Repeat the test with an explicitly restricted source document. Check retrieval, citations, suggestions, and both cache tiers for ordinary users and admins.
