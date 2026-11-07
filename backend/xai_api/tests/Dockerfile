# Reuse the already pinned numerical and auth environments, without downloading.
FROM harpisense-admin-mfa-http:latest AS auth
FROM harpisense-detection:integration
COPY --from=auth /usr/local/lib/python3.12/site-packages/ /usr/local/lib/python3.12/site-packages/
RUN python -c "import sklearn,numpy,pandas,cryptography,pyotp,fastapi,psycopg,jsonschema; print('XAI_TEST_DEPENDENCIES_OK')"
ENV PYTHONPATH=/work/backend/domain:/work/backend:/work/genai
WORKDIR /work
