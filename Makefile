setup_dev:
	poetry install --only dev

shell: setup_dev
	/bin/bash
