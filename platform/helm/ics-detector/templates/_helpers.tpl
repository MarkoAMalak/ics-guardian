{{- define "ics-detector.name" -}}
{{- .Chart.Name -}}
{{- end -}}

{{- define "ics-detector.labels" -}}
app.kubernetes.io/name: {{ include "ics-detector.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: ics-devsecops-platform
{{- end -}}

{{- define "ics-detector.selectorLabels" -}}
app.kubernetes.io/name: {{ include "ics-detector.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}
