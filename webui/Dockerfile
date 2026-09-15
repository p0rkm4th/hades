FROM ghcr.io/open-webui/open-webui@sha256:6bb1fbe8ab0a3e0456067f493044ffb66a30a65a34be47f6a5862176a370dd16

COPY hades-theme.css /app/backend/open_webui/static/hades-theme.css
COPY hades-theme.js /app/backend/open_webui/static/hades-theme.js
COPY channel_response_compat.py /opt/hades/channel_response_compat.py
COPY entrypoint.sh /opt/hades/entrypoint.sh
RUN python3 /opt/hades/channel_response_compat.py \
    && rm -f /opt/hades/channel_response_compat.py
RUN chmod 0555 /opt/hades/entrypoint.sh
ENTRYPOINT ["/opt/hades/entrypoint.sh"]
CMD ["bash", "start.sh"]
