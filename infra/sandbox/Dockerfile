# Reps learner-code sandbox image.
# Pinned runtime; standard library only. The harness is baked in and read-only at runtime.
FROM python:3.12.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONHASHSEED=0

# Remove package tooling that learner code has no reason to reach.
RUN rm -rf /usr/local/lib/python3.12/ensurepip /usr/local/bin/pip* /root/.cache \
    && mkdir -p /opt/reps

COPY harness/runner.py /opt/reps/runner.py
RUN chmod 0444 /opt/reps/runner.py && chmod 0555 /opt/reps

USER 65534:65534
WORKDIR /tmp
ENTRYPOINT ["python", "-I", "-B", "/opt/reps/runner.py"]
