FROM alpine:3.20

# postgresql16-client matches the server image (postgres:16-alpine).
# rclone is optional and small; included so offsite backup works out of
# the box once RCLONE_REMOTE is configured — it sits idle otherwise.
RUN apk add --no-cache postgresql16-client bash tzdata rclone

WORKDIR /app
COPY backup.sh /app/backup.sh
COPY crontab /etc/crontabs/root
RUN chmod +x /app/backup.sh

CMD ["crond", "-f", "-l", "2"]
