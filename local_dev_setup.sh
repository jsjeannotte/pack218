 #!/bin/bash
 ./copy_db_from_prod.sh
 ./venv_create.sh
 ./deps_sync.sh
 echo "Local development setup complete"
 echo "Run the following command to start the development server:"
 echo "./local_dev_run.sh"
 