ARG OPEN_WEBUI_BASE_IMAGE=ghcr.io/open-webui/open-webui@sha256:6bb1fbe8ab0a3e0456067f493044ffb66a30a65a34be47f6a5862176a370dd16
FROM ${OPEN_WEBUI_BASE_IMAGE}

COPY webui/hades-theme.css /app/backend/open_webui/static/hades-theme.css
COPY webui/hades-theme.js /app/backend/open_webui/static/hades-theme.js
# Open WebUI rebuilds backend/static from frontend/static during startup.
# Put this injected asset in the frontend build so it survives that sync.
COPY webui/hades-theme.css /app/build/static/hades-theme.css
COPY webui/hades-theme.js /app/build/static/hades-theme.js
COPY webui/finance-upload.js /app/build/static/finance-upload.js
COPY webui/finance_upload_compat.py /opt/hades/finance_upload_compat.py
COPY webui/receipt-upload.js /app/build/static/receipt-upload.js
COPY webui/receipt_upload_compat.py /opt/hades/receipt_upload_compat.py
COPY webui/configure_fast_route.py /opt/hades/configure_fast_route.py
COPY webui/streaming_compat.py /opt/hades/streaming_compat.py
COPY webui/stream_disconnect_compat.py /opt/hades/stream_disconnect_compat.py
COPY webui/hades_stream_disconnect_compat.py /opt/hades/hades_stream_disconnect_compat.py
COPY integrations/actual-finance-import /opt/hades/finance-import
COPY webui/channel_response_compat.py /opt/hades/channel_response_compat.py
COPY webui/entrypoint.sh /opt/hades/entrypoint.sh
RUN python3 /opt/hades/channel_response_compat.py \
    && python3 /opt/hades/finance_upload_compat.py \
    && python3 /opt/hades/receipt_upload_compat.py \
    && python3 /opt/hades/streaming_compat.py \
    && python3 /opt/hades/stream_disconnect_compat.py \
    && cp /opt/hades/hades_stream_disconnect_compat.py /app/backend/open_webui/utils/hades_stream_disconnect_compat.py \
    && rm -f /opt/hades/channel_response_compat.py
# Open WebUI serves injected assets from backend/static after its startup
# synchronization. Keep that served copy aligned with the patched build copy.
RUN cp /app/build/static/hades-theme.css /app/backend/open_webui/static/hades-theme.css \
    && cp /app/build/static/hades-theme.js /app/backend/open_webui/static/hades-theme.js
RUN chmod 0555 /opt/hades/entrypoint.sh
ENTRYPOINT ["/opt/hades/entrypoint.sh"]
CMD ["bash", "start.sh"]
