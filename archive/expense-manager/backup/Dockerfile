# pg_dump from the same major version as the db service; alpine image is arm64-native
FROM postgres:16-alpine
RUN apk add --no-cache rclone tzdata
COPY backup.sh /usr/local/bin/backup.sh
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/backup.sh /usr/local/bin/entrypoint.sh
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
