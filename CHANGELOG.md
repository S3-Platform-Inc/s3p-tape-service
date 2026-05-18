## [1.0.3](https://github.com/S3-Platform-Inc/s3p-tape-service/compare/v1.0.2...v1.0.3) (2026-05-18)

### Bug Fixes

* **docker:** update service images to use GitHub Container Registry and enhance session cookie configuration ([7e2129f](https://github.com/S3-Platform-Inc/s3p-tape-service/commit/7e2129ffa10347ab8d7c217f687e966b779c2617))

## [1.0.2](https://github.com/S3-Platform-Inc/s3p-tape-service/compare/v1.0.1...v1.0.2) (2026-05-16)

### Bug Fixes

* **tests:** honor REDIS_PASSWORD from env/.env in integration conftest ([e1fd92b](https://github.com/S3-Platform-Inc/s3p-tape-service/commit/e1fd92b7632c8f3e26d4948cec7d52f826a00574))
* **tests:** improve database URL handling with clearer formatting ([1a3f18d](https://github.com/S3-Platform-Inc/s3p-tape-service/commit/1a3f18dd51d6bcce9d88e1cc86b97726002fce93))
* update user privileges to use 'bot' key and enhance database URL handling in tests ([9611757](https://github.com/S3-Platform-Inc/s3p-tape-service/commit/9611757ff1258817334dcfb9dc6a4255c2e4fac5))

## [1.0.1](https://github.com/S3-Platform-Inc/s3p-tape-service/compare/v1.0.0...v1.0.1) (2026-05-15)

### Bug Fixes

* **docker:** set SHELL with pipefail to harden curl|sh uv install ([d0f7654](https://github.com/S3-Platform-Inc/s3p-tape-service/commit/d0f76544deaa8fd0d07431af5d15032f7145d4ce))

## 1.0.0 (2026-05-15)

### Features

* **svc-1:** Dockerfile + compose for api + worker ([14f203f](https://github.com/S3-Platform-Inc/s3p-tape-service/commit/14f203ff084f7079b2775e059e9079d29f1abe5a))
* **svc-1:** FastAPI app, /health, lifespan-managed DB pool ([8e66f49](https://github.com/S3-Platform-Inc/s3p-tape-service/commit/8e66f49798da59e79058efb772b94f547c6e538c))
* **svc-1:** JSON logging with secret redaction ([9f1b5fd](https://github.com/S3-Platform-Inc/s3p-tape-service/commit/9f1b5fd1b95956f4a761c2a36eff2b27e4f96a61))
* **svc-1:** machine-readable error model ([4cfa2e8](https://github.com/S3-Platform-Inc/s3p-tape-service/commit/4cfa2e8a2c56226dc73a3d12850afb4d15dc907d))
* **svc-1:** psycopg connection pool lifecycle ([47217ea](https://github.com/S3-Platform-Inc/s3p-tape-service/commit/47217ea750d0795341c19c5a004a9e72e2c7e7e1))
* **svc-1:** typed env settings with pydantic-settings ([714c857](https://github.com/S3-Platform-Inc/s3p-tape-service/commit/714c8579625417fc10044751675542b69fcab91a))
* **svc-1:** worker entrypoint with apscheduler heartbeat ([3a4d7dd](https://github.com/S3-Platform-Inc/s3p-tape-service/commit/3a4d7ddcbb101bd09c3be80a9fe97303e5130a29))
* **svc-2:** db schema-presence probes + seeded integration fixture ([c92d933](https://github.com/S3-Platform-Inc/s3p-tape-service/commit/c92d933ac689d5f05177c5c1275e70f99e81e356))
* **svc-2:** documents.fetch_by_ids + score.save wrappers, tag svc-2 ([13bdd54](https://github.com/S3-Platform-Inc/s3p-tape-service/commit/13bdd547c2e406f75d32c888ad982cf8e7fa0179))
* **svc-2:** redis store — client, sessions, tape state, advisory lock ([38e6e78](https://github.com/S3-Platform-Inc/s3p-tape-service/commit/38e6e78cfbdd1c99fe5fb5e9907209dc7f1902c0))
* **svc-2:** redis-backed compose + dev-stack-backed integration tests ([76a3a29](https://github.com/S3-Platform-Inc/s3p-tape-service/commit/76a3a29eaeec8d10dcdc1ea28b761ec17e7bb33a))
* **svc-2:** seed docs/sql/ with dev platform DB + auth_by_token + score-notify ([177fec2](https://github.com/S3-Platform-Inc/s3p-tape-service/commit/177fec21325ac78ab15de509f2fbc323a9f197f2))
* **svc-2:** users.auth_by_token + sources + roles wrappers ([414d593](https://github.com/S3-Platform-Inc/s3p-tape-service/commit/414d593be577ed442175b0150e65f2118913dde0))
* **svc-3:** /auth/login, /auth/logout, /auth/me + tag svc-3 ([f9819b8](https://github.com/S3-Platform-Inc/s3p-tape-service/commit/f9819b8f29c7b1fe9f3f79da7a4737f9a8133cb9))
* **svc-3:** current_user FastAPI dependency + auth schemas ([e5fd54d](https://github.com/S3-Platform-Inc/s3p-tape-service/commit/e5fd54db963abc56a158eb08d25dafe8ad2bff28))
* **svc-3:** in-process per-IP login rate limit ([9aba823](https://github.com/S3-Platform-Inc/s3p-tape-service/commit/9aba8232298b7c2e34c2a384802fdbbeac062c6c))
* **svc-4:** config schemas + sources.fetch_names_by_ids ([56b070e](https://github.com/S3-Platform-Inc/s3p-tape-service/commit/56b070ee54047557504101b11dd908b664edf6e7))
* **svc-4:** GET/PUT /config + tag svc-4 ([f3e9046](https://github.com/S3-Platform-Inc/s3p-tape-service/commit/f3e9046f5a10ba5361b35db7cd0a8f429a47755b))
* **svc-5:** generator — candidates query, list users, generate_for_user, tick ([c0bdb86](https://github.com/S3-Platform-Inc/s3p-tape-service/commit/c0bdb8618c9a3968142717a377760138a54d17b4))
* **svc-5:** score-notify listener thread → Redis remove_entry ([b1fc68b](https://github.com/S3-Platform-Inc/s3p-tape-service/commit/b1fc68b4c25e46b5f21b4bb0342e55dff5a0505e))
* **svc-5:** wire generator into scheduler + listener into worker entry; tag svc-5 ([6c7a85b](https://github.com/S3-Platform-Inc/s3p-tape-service/commit/6c7a85bbba1d8d3f368c28a6cbe1d623aa35fbb6))
* **svc-6:** GET /tape + POST /score + tag svc-6 ([1f5d63d](https://github.com/S3-Platform-Inc/s3p-tape-service/commit/1f5d63ddcaa97d33f783d1c3b2284af2a5e9eecd))
* **svc-6:** tape + score schemas and roles.fetch_names_by_ids ([58d15be](https://github.com/S3-Platform-Inc/s3p-tape-service/commit/58d15bed5b01cf27f1087e6b3953276910771653))
* **svc-7:** non-root container, prod compose overlay, docs/DEPLOY.md, README polish ([aea2065](https://github.com/S3-Platform-Inc/s3p-tape-service/commit/aea206509e72cfaa59ee5c44161dc97e0481566b))

### Bug Fixes

* **svc-7:** Dockerfile CMD uses console-script; copy README during build ([de308d6](https://github.com/S3-Platform-Inc/s3p-tape-service/commit/de308d6580fda67c290cd51b53af86cd8bb44291))
