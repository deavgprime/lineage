{{- define "lineage.tag" -}}{{ .Values.image.tag | default .Chart.AppVersion }}{{- end }}

{{- define "lineage.labels" -}}
app.kubernetes.io/part-of: lineage
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ include "lineage.tag" . | quote }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
{{- end }}

{{/* Pods run as a non-root user on a read-only root filesystem with no capabilities. */}}
{{- define "lineage.podSecurity" -}}
automountServiceAccountToken: false
securityContext:
  runAsNonRoot: true
  seccompProfile:
    type: RuntimeDefault
{{- end }}

{{- define "lineage.containerSecurity" -}}
securityContext:
  allowPrivilegeEscalation: false
  readOnlyRootFilesystem: true
  capabilities:
    drop: ["ALL"]
{{- end }}

{{/* Environment shared by the API, the migration job and the ingestion job. */}}
{{- define "lineage.apiEnv" -}}
- name: DATABASE_URL
  valueFrom:
    secretKeyRef: { name: {{ .Values.existingSecret }}, key: DATABASE_URL }
- name: LINEAGE_MODELS
  value: /tmp/models
- name: HOME
  value: /tmp
{{- end }}
