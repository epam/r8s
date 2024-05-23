# MinIO Installation & Configuration on Linux

### Installation:
To install MinIO on your Linux machine go to the official [link](https://min.io/download#/linux)
and follow the installation steps according to your package manager. You should
install MinIO server and client.

Or you can follow this:
- Download server binary package:

  ```bash
  $ wget https://dl.min.io/server/minio/release/linux-amd64/minio
  ```

- Make the retrieved file executable:

  ```bash
  $ chmod +x minio
  ```

- Download client binary package:

  ```bash
  $ wget https://dl.min.io/client/mc/release/linux-amd64/mc
  ```

- Make the retrieved file executable:

  ```bash
  $ chmod +x mc
  ```

- Check whether MinIO server `minio` and MinIO client `mc` work - execute 
them one by one:
  ```bash
  $ ./minio --help
  NAME:
    minio.exe - High Performance Object Storage

  DESCRIPTION:
  ...
  ```
  ```bash
  $ ./mc --help
  NAME:
    mc - MinIO Client for cloud storage and filesystems.

  USAGE:
    mc [FLAGS] COMMAND [COMMAND FLAGS | -h] [ARGUMENTS...]
  ...
  ```
*None:* make sure you are in the same directory there binaries are situated or
add the folder with them to PATH:
  ```bash
  $ ls
  mc  minio
  $ export PATH=$PATH:$PWD
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

- Go to http://127.0.0.1:41149/users/ and create new user. Enter access key and secret key and save them, we will use them later. Select consoleAdmin policy. Then save.


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