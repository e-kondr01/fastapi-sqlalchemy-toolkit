test:
	docker compose -f tests/docker-compose.yml up -d
	docker build -t test_toolkit:latest --file tests/Dockerfile .
	- docker run --name toolkit-test --network toolkit-test test_toolkit:latest
	docker rm toolkit-test
	docker compose -f tests/docker-compose.yml down

docs_publish:
	mkdocs build
	mkdocs gh-deploy