# MinIO Installation & Configuration on MacOS


### Installation

Run the following command to install the latest stable MinIO package 
using Homebrew:
```
brew install minio/stable/minio
```
2. Install MinIO client (mc) packages:
```
brew install minio/stable/mc
```

### Configuration:

- Set root credentials for MinIO server:

  ```bash
  $ export MINIO_ROOT_USER={YOUR_USER_NAME}
  $ export MINIO_ROOT_PASSWORD={YOUR_USER_PASSWORD}
  ```

- Start MinIO server locally:

  ```bash
  minio server ~/minio --console-address 0.0.0.0:41149
  ```

- Configure MinIO client targeting on the started server:

  ```bash
  $ mc alias set myminio http://127.0.0.1:9000 $MINIO_ROOT_USER $MINIO_ROOT_PASSWORD
  ```

- Make up your access and secret keys for a user which will be used to access the server:

  ```bash
  $ export MINIO_ACCESS_KEY={YOUR_ACCESS_KEY}
  $ export MINIO_SECRET_ACCESS_KEY={YOUR_SECRET_KEY}
  ```

- Create MinIO user with you just set access keys:

  ```bash
  $ mc admin user add myminio $MINIO_ACCESS_KEY $MINIO_SECRET_ACCESS_KEY
  ```
  
- Assign the policy consoleAdmin to the created user to make him be able to perform various commands:

  ```bash
  $ mc admin policy attach myminio consoleAdmin --user $MINIO_ACCESS_KEY
  ```