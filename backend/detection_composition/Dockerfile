FROM harpisense-backend:integration
COPY backend/detection_composition/requirements.txt /tmp/composition-requirements.txt
RUN python -m pip install --no-cache-dir -r /tmp/composition-requirements.txt
ENV PYTHONPATH=/work/backend/domain:/work/backend:/work/genai
WORKDIR /work
