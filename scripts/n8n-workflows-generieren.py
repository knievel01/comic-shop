#!/usr/bin/env python3
# Generates the initial n8n workflow JSON in workflows/. After the first import the n8n UI is
# the source of truth: edit there, then scripts/n8n-export.sh. Kept for reference/re-creation.
import json, pathlib, uuid
OUT = pathlib.Path(__file__).resolve().parents[1] / "workflows"
HELPER = "http://comic-helper.comics.svc.cluster.local:8080"
CRED_HELPER = {"httpHeaderAuth": {"id": "cmxHelperToken01", "name": "Comic Helper Token"}}
CRED_SMTP = {"smtp": {"id": "cmxSmtpComics001", "name": "SMTP Comics"}}
ERROR_WF = "cmxFehlerAlarm01"

def nid(name):  # stable node ids -> clean diffs
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "comics/" + name))

def node(name, type_, ver, pos, params, **extra):
    n = {"id": nid(name), "name": name, "type": type_, "typeVersion": ver, "position": pos, "parameters": params}
    n.update(extra)
    return n

def http(name, pos, method, url, body=None, timeout=60000, **extra):
    p = {"method": method, "url": url, "authentication": "genericCredentialType",
         "genericAuthType": "httpHeaderAuth", "options": {"timeout": timeout}}
    if body is not None:
        p.update(sendBody=True, specifyBody="json", jsonBody=body)
    return node(name, "n8n-nodes-base.httpRequest", 4.2, pos, p, credentials=CRED_HELPER, **extra)

def conn(*pairs):
    c = {}
    for src, dst, out in pairs:
        c.setdefault(src, {"main": []})
        while len(c[src]["main"]) <= out:
            c[src]["main"].append([])
        if dst:
            c[src]["main"][out].append({"node": dst, "type": "main", "index": 0})
    return c

def wf(wid, name, nodes, connections, error_wf=True):
    settings = {"executionOrder": "v1", "timezone": "Europe/Berlin", "saveDataSuccessExecution": "none",
                "saveDataErrorExecution": "all"}
    if error_wf:
        settings["errorWorkflow"] = ERROR_WF
    return {"id": wid, "name": name, "active": False, "nodes": nodes, "connections": connections,
            "settings": settings, "pinData": {}, "meta": {"templateCredsSetupCompleted": False},
            "tags": []}

flows = []

# Phase 5/6: ingest + recognition
flows.append(wf("cmxScanIngest001", "Comics 01 Scan-Ingest und Erkennung", [
    node("Alle 2 Minuten", "n8n-nodes-base.scheduleTrigger", 1.2, [0, 0],
         {"rule": {"interval": [{"field": "minutes", "minutesInterval": 2}]}}),
    http("Neue Scans holen", [220, 0], "POST", f"={HELPER}/api/scans/claim?limit=20"),
    node("Einzeln", "n8n-nodes-base.splitOut", 1, [440, 0], {"fieldToSplitOut": "ids", "options": {}}),
    http("Erkennen (Claude)", [660, 0], "POST", f"={HELPER}/api/scans/{{{{ $json.ids }}}}/recognize",
         timeout=300000, onError="continueErrorOutput", retryOnFail=True, maxTries=3, waitBetweenTries=5000),
    node("Erkannt", "n8n-nodes-base.noOp", 1, [900, -100], {}),
    http("Fehlerpfad: als Fehler markieren", [900, 100], "POST",
         f"={HELPER}/api/scans/{{{{ $('Einzeln').item.json.ids }}}}/fail",
         body="={{ JSON.stringify({ fehler: $json.error?.message || JSON.stringify($json.error || $json) }) }}"),
], conn(("Alle 2 Minuten", "Neue Scans holen", 0), ("Neue Scans holen", "Einzeln", 0),
        ("Einzeln", "Erkennen (Claude)", 0), ("Erkennen (Claude)", "Erkannt", 0),
        ("Erkennen (Claude)", "Fehlerpfad: als Fehler markieren", 1))))

# Phase 9 + 8: Shopify first, then metadata/move
flows.append(wf("cmxShopify000001", "Comics 02 Bestätigt nach Shopify und aktiv", [
    node("Webhook vom Review", "n8n-nodes-base.webhook", 2, [0, 0],
         {"httpMethod": "POST", "path": "comic-bestaetigt", "authentication": "headerAuth",
          "responseMode": "onReceived", "options": {}},
         credentials={"httpHeaderAuth": CRED_HELPER["httpHeaderAuth"]}, webhookId=nid("wh-bestaetigt")),
    node("ID aus Webhook", "n8n-nodes-base.set", 3.4, [220, 0],
         {"mode": "manual", "assignments": {"assignments": [
             {"id": nid("a1"), "name": "id", "type": "string", "value": "={{ $json.body.id }}"}]}, "options": {}}),
    node("Alle 15 Minuten (Nachzügler)", "n8n-nodes-base.scheduleTrigger", 1.2, [0, 220],
         {"rule": {"interval": [{"field": "minutes", "minutesInterval": 15}]}}),
    http("Bestätigte ohne Shop holen", [220, 220], "GET", f"={HELPER}/api/scans/confirmed"),
    node("Einzeln", "n8n-nodes-base.splitOut", 1, [440, 220], {"fieldToSplitOut": "ids", "destinationFieldName": "id", "options": {}}),
    http("Shopify: Variante anlegen", [700, 100], "POST", f"={HELPER}/api/scans/{{{{ $json.id }}}}/shopify",
         onError="continueErrorOutput", retryOnFail=True, maxTries=3, waitBetweenTries=10000),
    http("S3: Metadaten und nach aktiv/", [940, 0], "POST",
         f"={HELPER}/api/scans/{{{{ $json.id }}}}/finalize", onError="continueErrorOutput"),
    node("Fertig", "n8n-nodes-base.noOp", 1, [1180, -100], {}),
    node("Später erneut (15-Min-Lauf)", "n8n-nodes-base.noOp", 1, [1180, 200], {},
         notes="Fehler bleiben im Status 'bestaetigt' und werden vom 15-Minuten-Lauf erneut versucht. "
               "Die Tagesmail zeigt 'Bestätigt, noch nicht im Shop'."),
], {
    **conn(("Webhook vom Review", "ID aus Webhook", 0), ("ID aus Webhook", "Shopify: Variante anlegen", 0),
           ("Alle 15 Minuten (Nachzügler)", "Bestätigte ohne Shop holen", 0),
           ("Bestätigte ohne Shop holen", "Einzeln", 0), ("Einzeln", "Shopify: Variante anlegen", 0),
           ("Shopify: Variante anlegen", "S3: Metadaten und nach aktiv/", 0),
           ("Shopify: Variante anlegen", "Später erneut (15-Min-Lauf)", 1),
           ("S3: Metadaten und nach aktiv/", "Fertig", 0),
           ("S3: Metadaten und nach aktiv/", "Später erneut (15-Min-Lauf)", 1)),
}))

# Phase 10: sales webhook
flows.append(wf("cmxVerkauf000001", "Comics 03 Shopify-Verkauf", [
    node("Shopify Webhook", "n8n-nodes-base.webhook", 2, [0, 0],
         {"httpMethod": "POST", "path": "shopify-orders", "responseMode": "responseNode",
          "options": {"rawBody": True}}, webhookId=nid("wh-shopify")),
    node("An comic-helper (HMAC-Prüfung)", "n8n-nodes-base.httpRequest", 4.2, [240, 0], {
        "method": "POST", "url": f"={HELPER}/api/shopify/webhook",
        "authentication": "genericCredentialType", "genericAuthType": "httpHeaderAuth",
        "sendHeaders": True, "headerParameters": {"parameters": [
            {"name": "X-Shopify-Hmac-Sha256", "value": "={{ $json.headers['x-shopify-hmac-sha256'] }}"},
            {"name": "X-Shopify-Topic", "value": "={{ $json.headers['x-shopify-topic'] }}"},
            {"name": "X-Shopify-Webhook-Id", "value": "={{ $json.headers['x-shopify-webhook-id'] }}"}]},
        "sendBody": True, "contentType": "binaryData", "inputDataFieldName": "data",
        "options": {"timeout": 30000}}, credentials=CRED_HELPER, onError="continueErrorOutput"),
    node("200 an Shopify", "n8n-nodes-base.respondToWebhook", 1.1, [480, -100],
         {"respondWith": "json", "responseBody": "={{ JSON.stringify($json) }}", "options": {"responseCode": 200}}),
    node("500 an Shopify (Shopify wiederholt)", "n8n-nodes-base.respondToWebhook", 1.1, [480, 100],
         {"respondWith": "text", "responseBody": "error", "options": {"responseCode": 500}}),
    node("Fehler melden", "n8n-nodes-base.stopAndError", 1, [720, 100],
         {"errorMessage": "={{ 'Verkaufs-Webhook fehlgeschlagen: ' + ($json.error?.message || 'unbekannt') }}"}),
], conn(("Shopify Webhook", "An comic-helper (HMAC-Prüfung)", 0),
        ("An comic-helper (HMAC-Prüfung)", "200 an Shopify", 0),
        ("An comic-helper (HMAC-Prüfung)", "500 an Shopify (Shopify wiederholt)", 1),
        ("500 an Shopify (Shopify wiederholt)", "Fehler melden", 0))))

# Phase 11: daily mail
flows.append(wf("cmxTagesmail0001", "Comics 04 Tagesmail 7 Uhr", [
    node("Täglich 7:00", "n8n-nodes-base.scheduleTrigger", 1.2, [0, 0],
         {"rule": {"interval": [{"field": "cronExpression", "expression": "0 7 * * *"}]}}),
    http("Zahlen holen", [220, 0], "GET", f"={HELPER}/api/report/daily?hours=24", retryOnFail=True, maxTries=3,
         waitBetweenTries=5000),
    node("Mail senden", "n8n-nodes-base.emailSend", 2.1, [440, 0], {
        "fromEmail": "={{ $json.absender }}",
        "toEmail": "={{ $json.empfaenger }}",
        "subject": "=Comics: {{ $json.gescannt }} gescannt, {{ $json.gesamt_offen }} offen",
        "emailFormat": "text",
        "text": "={{ $json.text }}\nZur Prüfung: {{ $json.review_url }}\n",
        "options": {}}, credentials=CRED_SMTP),
], conn(("Täglich 7:00", "Zahlen holen", 0), ("Zahlen holen", "Mail senden", 0))))

# Phase 12: error workflow
flows.append(wf(ERROR_WF, "Comics 99 Fehler-Alarm", [
    node("Bei Workflow-Fehler", "n8n-nodes-base.errorTrigger", 1, [0, 0], {}),
    http("Empfänger holen", [220, 0], "GET", f"={HELPER}/api/mail-config", onError="continueRegularOutput"),
    node("Alarm-Mail", "n8n-nodes-base.emailSend", 2.1, [440, 0], {
        "fromEmail": "={{ $json.from }}",
        "toEmail": "={{ $json.alerts }}",
        "subject": "=Comic-Automatisierung: Fehler in {{ $('Bei Workflow-Fehler').item.json.workflow.name }}",
        "emailFormat": "text",
        "text": "=Workflow: {{ $('Bei Workflow-Fehler').item.json.workflow.name }}\n"
                "Node: {{ $('Bei Workflow-Fehler').item.json.execution.lastNodeExecuted }}\n"
                "Fehler: {{ $('Bei Workflow-Fehler').item.json.execution.error.message }}\n"
                "Ausführung: {{ $('Bei Workflow-Fehler').item.json.execution.url }}\n",
        "options": {}}, credentials=CRED_SMTP),
], conn(("Bei Workflow-Fehler", "Empfänger holen", 0), ("Empfänger holen", "Alarm-Mail", 0)), error_wf=False))

import re
for f in flows:
    slug = re.sub(r"[^a-z0-9]+", "-", f["name"].lower().replace("ä", "ae").replace("ü", "ue").replace("ö", "oe")).strip("-")
    (OUT / f"{slug}.json").write_text(json.dumps(f, indent=2, ensure_ascii=False) + "\n")
    print(slug)
