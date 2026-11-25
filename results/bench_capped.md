# 2 GB memory cap vs unconstrained (m=16)

Capped run: original vectors on disk, quantized copies in RAM, container limited to 2 GB. Latency is Qdrant's server-side search time. `ram_capped_mb` is from `docker stats`, which excludes page cache, so float32 (read from disk) looks small; compare it with the in-RAM size of each representation (float32 about 3,000 MB, int8 about 770 MB, binary about 100 MB).

| mode | ef | recall_free | recall_capped | p95_free_ms | p95_capped_ms | slowdown | ram_capped_mb |
|---|---|---|---|---|---|---|---|
| float32 | 32 | 0.898 | 0.906 | 4.790 | 9.050 | 1.889 | 121 |
| float32 | 64 | 0.940 | 0.943 | 6.680 | 10.930 | 1.636 | 122 |
| float32 | 128 | 0.966 | 0.966 | 8.230 | 14.380 | 1.747 | 122 |
| float32 | 256 | 0.981 | 0.978 | 10.700 | 19.180 | 1.793 | 122 |
| scalar | 32 | 0.906 | 0.903 | 4.250 | 7.870 | 1.852 | 898 |
| scalar | 64 | 0.943 | 0.942 | 5.600 | 9.340 | 1.668 | 899 |
| scalar | 128 | 0.968 | 0.964 | 6.280 | 11.710 | 1.865 | 899 |
| scalar | 256 | 0.977 | 0.976 | 6.720 | 13.150 | 1.957 | 899 |
| binary | 32 | 0.884 | 0.873 | 2.150 | 6.650 | 3.093 | 272 |
| binary | 64 | 0.919 | 0.904 | 3.370 | 7.650 | 2.270 | 272 |
| binary | 128 | 0.931 | 0.920 | 4.020 | 8.970 | 2.231 | 271 |
| binary | 256 | 0.939 | 0.927 | 4.590 | 11.540 | 2.514 | 272 |
