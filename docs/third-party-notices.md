# Third-Party Notices

## Direct Dependencies

| Name | URL | Version | License | Purpose | Integration Mode | Upstream Modified? | Update Owner |
|---|---|---|---|---|---|---|---|
| sentence-transformers | https://github.com/UKPLab/sentence-transformers | >=2.2.0 | Apache-2.0 | Semantic text similarity | Python dependency | No | Dev A |
| all-MiniLM-L6-v2 | https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2 | v2 | Apache-2.0 | Pre-trained SBERT model | Bundled weights | No | Dev A |
| Flask | https://flask.palletsprojects.com/ | 3.0.3 | BSD-3-Clause | Mock marketplace server | Python dependency | No | Dev A |
| requests | https://requests.readthedocs.io/ | 2.32.3 | Apache-2.0 | HTTP client with SOCKS | Python dependency | No | Dev A |
| beautifulsoup4 | https://www.crummy.com/software/BeautifulSoup/ | 4.12.3 | MIT | HTML parsing | Python dependency | No | Dev A |
| PySocks | https://github.com/Anorov/PySocks | >=1.7.1 | BSD | SOCKS proxy support | Python dependency | No | Dev A |
| Streamlit | https://streamlit.io/ | >=1.30.0 | Apache-2.0 | Analyst dashboard UI | Python dependency | No | Dev B |
| pandas | https://pandas.pydata.org/ | >=2.0.0 | BSD-3-Clause | Data manipulation | Python dependency | No | Dev B |
| networkx | https://networkx.org/ | >=3.0 | BSD-3-Clause | Graph data structures | Python dependency | No | Dev B |
| pyvis | https://pyvis.readthedocs.io/ | >=0.3.0 | BSD | Graph visualization | Python dependency | No | Dev B |
| reportlab | https://www.reportlab.com/ | >=4.0.0 | BSD | PDF report generation | Python dependency | No | Dev B |
| PostgreSQL | https://www.postgresql.org/ | 16 | PostgreSQL License | Canonical data store | Docker service | No | Dev A |
| MinIO | https://min.io/ | latest | AGPL-3.0 | Immutable artifact storage | Docker service | No | Dev A |
| Neo4j Community | https://neo4j.com/ | 5.x | GPL-3.0 | Graph projection backend | Docker service | No | Dev A |
| nao1215/onionscan | https://github.com/nao1215/onionscan | pinned | MIT | Onion OPSEC scanning | Pinned binary/container | No | Dev A |
| pystylometry | https://github.com/jpotts18/pystylometry | latest | MIT | Classical stylometry features | Python dependency | No | Dev A |
| scikit-learn | https://scikit-learn.org/ | >=1.3.0 | BSD-3-Clause | ML utilities for stylometry | Python dependency | No | Dev A |
| Nginx | https://nginx.org/ | Alpine | BSD-2-Clause | Mock web servers | Docker image | No | Dev A |
| Tor | https://www.torproject.org/ | Debian bookworm | BSD-3-Clause | Hidden service publishing, SOCKS proxy | Docker service | No | Dev A |

## Planned Dependencies (not yet added)

| Name | Purpose | Planned Branch |
|---|---|---|
| FastAPI | REST API framework | Branch 5 |
| uvicorn | ASGI server | Branch 5 |
| pydantic | Data validation models | Branch 1 |
| alembic | Database migrations | Branch 1 |
| psycopg2 | PostgreSQL driver | Branch 1 |
| minio | MinIO Python client | Branch 2 |
| neo4j | Neo4j Python driver | Branch 10 |
| pyjwt | JWT authentication | Branch 5 |
| pytest | Testing framework | Branch 0 |
| flake8 | Linting | Branch 0 |
| bandit | Security scanning | Branch 0 |

## Notes
- All Docker images should be pinned by digest in production
- Python dependencies are pinned in requirements.txt / lock file
- SBOM generation will be added to CI pipeline
- Offline artifact manifest for demo deployment maintained in fixtures/manifests/
