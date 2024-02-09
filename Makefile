test:
	docker compose -f tests/infra/test-docker-compose.yml up -d
	docker build -t test_toolkit:latest --file tests/infra/Dockerfile_test .
	- docker run --name toolkit_tests --network toolkit-test test_toolkit:latest
	docker container rm toolkit_tests
	docker compose -f tests/infra/test-docker-compose.yml down
