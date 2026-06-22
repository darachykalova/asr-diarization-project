FROM alpine:3.19

RUN apk add --no-cache postgresql-client curl bash

# MinIO client
RUN curl -sSL https://dl.min.io/client/mc/release/linux-amd64/mc -o /usr/local/bin/mc \
    && chmod +x /usr/local/bin/mc

COPY backup.sh /backup.sh
RUN chmod +x /backup.sh

# Run backup on a cron schedule (default: 2:00 AM daily)
RUN echo "0 2 * * * /backup.sh >> /var/log/backup.log 2>&1" | crontab -

CMD ["crond", "-f", "-l", "2"]
