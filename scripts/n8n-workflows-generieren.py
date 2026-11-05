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

def http(name, pos, method, url, body=None, timeout=60000, headers=None, **extra):
    p = {"method": method, "url": url, "authentication": "genericCredentialType",
         "genericAuthType": "httpHeaderAuth", "options": {"timeout": timeout}}
    if headers:
        p.update(sendHeaders=True, specifyHeaders="keypair",
                 headerParameters={"parameters": [{"name": k, "value": v} for k, v in headers.items()]})
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

# Successful runs are stored only for workflows that run rarely and on events (confirmation, daily mail),
# so the execution list shows what happened. 01 polls every 2 minutes and 99 only runs on errors: errors are
# stored for all, successes of 01 would be ~700 empty entries a day.
SAVE_SUCCESS = {"cmxShopify000001", "cmxTagesmail0001"}


def wf(wid, name, nodes, connections, error_wf=True):
    settings = {"executionOrder": "v1", "timezone": "Europe/Berlin",
                "saveDataSuccessExecution": "all" if wid in SAVE_SUCCESS else "none",
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
    node("Webhook Foto-Upload", "n8n-nodes-base.webhook", 2, [0, 220],
         {"httpMethod": "POST", "path": "scan-neu", "authentication": "headerAuth",
          "responseMode": "onReceived", "options": {}},
         credentials={"httpHeaderAuth": CRED_HELPER["httpHeaderAuth"]}, webhookId=nid("wh-scan-neu"),
         notes="Die Review ruft das nach jedem Foto-Upload auf, damit die Erkennung sofort startet."),
    http("Neue Scans holen", [220, 0], "POST", f"={HELPER}/api/scans/claim?limit=20"),
    node("Einzeln", "n8n-nodes-base.splitOut", 1, [440, 0], {"fieldToSplitOut": "ids", "options": {}}),
    http("Erkennen (Claude)", [660, 0], "POST", f"={HELPER}/api/scans/{{{{ $json.ids }}}}/recognize",
         timeout=300000, headers={"X-N8N-Lauf": "={{ $execution.id }}"},
         onError="continueErrorOutput", retryOnFail=True, maxTries=3, waitBetweenTries=5000),
    node("Erkannt", "n8n-nodes-base.noOp", 1, [900, -100], {}),
    http("Fehlerpfad: als Fehler markieren", [900, 100], "POST",
         f"={HELPER}/api/scans/{{{{ $('Einzeln').item.json.ids }}}}/fail",
         body="={{ JSON.stringify({ fehler: $json.error?.message || JSON.stringify($json.error || $json) }) }}"),
], conn(("Alle 2 Minuten", "Neue Scans holen", 0), ("Webhook Foto-Upload", "Neue Scans holen", 0),
        ("Neue Scans holen", "Einzeln", 0),
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

# ---- Presentation for non-technical viewers: plain German node names, one-line captions under each node
# and coloured sticky notes that group the steps. Applied last so the logic above stays readable.
RENAMES = {
    "cmxScanIngest001": {
        "Alle 2 Minuten": "Alle 2 Minuten nachsehen",
        "Webhook Foto-Upload": "Foto wurde hochgeladen",
        "Neue Scans holen": "Neue Scans abholen",
        "Einzeln": "Ein Comic nach dem anderen",
        "Erkennen (Claude)": "KI liest das Cover",
        "Erkannt": "Fertig: wartet auf Prüfung",
        "Fehlerpfad: als Fehler markieren": "Problem vermerken",
    },
    "cmxShopify000001": {
        "Webhook vom Review": "Du klickst „Bestätigen“",
        "ID aus Webhook": "Comic merken",
        "Alle 15 Minuten (Nachzügler)": "Alle 15 Minuten Nachzügler suchen",
        "Bestätigte ohne Shop holen": "Bestätigte Comics suchen",
        "Einzeln": "Ein Comic nach dem anderen",
        "Shopify: Variante anlegen": "Im Shop anlegen",
        "S3: Metadaten und nach aktiv/": "Als „im Shop“ ablegen",
        "Fertig": "Fertig: Comic ist im Shop",
        "Später erneut (15-Min-Lauf)": "Klappt später nochmal",
    },
    "cmxTagesmail0001": {
        "Täglich 7:00": "Jeden Morgen um 7 Uhr",
        "Zahlen holen": "Zahlen von gestern zusammenstellen",
        "Mail senden": "Mail schreiben",
    },
    "cmxFehlerAlarm01": {
        "Bei Workflow-Fehler": "Irgendwo ist etwas schiefgelaufen",
        "Empfänger holen": "Empfänger nachschlagen",
        "Alarm-Mail": "Alarm-Mail senden",
    },
}
CAPTIONS = {
    "Alle 2 Minuten nachsehen": "Startet von selbst",
    "Neue Scans abholen": "Was liegt im Eingang?",
    "Foto wurde hochgeladen": "Startet sofort, ohne Warten",
    "KI liest das Cover": "Titel, Heft, Verlag, Zustand",
    "Fertig: wartet auf Prüfung": "Du prüfst in der Review",
    "Problem vermerken": "Comic bekommt Status Fehler",
    "Du klickst „Bestätigen“": "Startet sofort",
    "Alle 15 Minuten Nachzügler suchen": "Sicherheitsnetz",
    "Im Shop anlegen": "Produkt, Preis, Bestand 1",
    "Als „im Shop“ ablegen": "Ordner aktiv/ im Archiv",
    "Fertig: Comic ist im Shop": "Taucht grau in der Review auf",
    "Klappt später nochmal": "Neuer Versuch in 15 Minuten",
    "Jeden Morgen um 7 Uhr": "Startet von selbst",
    "Zahlen von gestern zusammenstellen": "Gescannt und geprüft",
    "Mail schreiben": "Ein Absatz, ein Link",
    "Irgendwo ist etwas schiefgelaufen": "Startet bei jedem Fehler",
    "Alarm-Mail senden": "An die Betreiber",
}


def sticky(key, pos, w, h, color, text):
    return {"id": nid("sticky/" + key), "name": "Notiz " + key, "type": "n8n-nodes-base.stickyNote",
            "typeVersion": 1, "position": pos,
            "parameters": {"content": text, "height": h, "width": w, "color": color}}


# colour 1 yellow, 2 orange, 3 blue, 4 green, 5 red, 6 purple, 7 grey
STICKIES = {
    "cmxScanIngest001": [
        ("titel", [-40, -360], 1120, 150, 7,
         "## So kommen neue Comics in die Review\nBei jedem Foto-Upload startet dieser Ablauf sofort, sonst schaut er alle 2 Minuten in den Eingang. "
         "Für jedes neue Scan liest die KI Titel, Heft, Verlag und Zustand aus dem Cover. "
         "Danach wartet das Comic auf deine Prüfung."),
        ("1", [-40, -190], 400, 330, 3, "### 1. Neue Scans finden"),
        ("2", [400, -190], 400, 330, 1, "### 2. KI liest das Cover\nBis zu 3 Versuche, falls es klemmt."),
        ("3", [860, -190], 220, 210, 4, "### Klappt"),
        ("4", [860, 40], 220, 230, 5, "### Klappt nicht"),
    ],
    "cmxShopify000001": [
        ("titel", [-40, -360], 1380, 150, 7,
         "## Vom Bestätigen bis in den Shop\nSobald du ein Comic bestätigst, legt dieser Ablauf es im Shop an "
         "(zunächst als Entwurf, für Kundschaft unsichtbar) und merkt sich das im Archiv. "
         "Alle 15 Minuten sucht er zusätzlich nach Comics, die er verpasst hat."),
        ("a", [-40, -190], 540, 190, 3, "### Auslöser 1: dein Klick"),
        ("b", [-40, 30], 560, 330, 6, "### Auslöser 2: Sicherheitsnetz"),
        ("c", [600, -190], 380, 360, 1, "### Im Shop anlegen\nBis zu 3 Versuche."),
        ("d", [1060, -190], 280, 210, 4, "### Klappt"),
        ("e", [1060, 130], 280, 230, 5, "### Klappt nicht\nKein Schaden: Das Comic bleibt bestätigt und wird später nochmal versucht."),
    ],
    "cmxTagesmail0001": [
        ("titel", [-40, -300], 760, 150, 7,
         "## Die Tagesmail\nJeden Morgen um 7 Uhr schickt dieser Ablauf eine kurze Zusammenfassung: "
         "wie viele Comics gescannt wurden und wie viele noch zu prüfen sind."),
    ],
    "cmxFehlerAlarm01": [
        ("titel", [-40, -300], 760, 150, 7,
         "## Der Alarm\nGeht in einem der anderen Abläufe etwas schief, meldet sich dieser Ablauf "
         "per Mail und nennt Ablauf, Schritt und Fehlermeldung."),
    ],
}

for f in flows:
    txt = json.dumps(f, ensure_ascii=False)
    for old, new in RENAMES.get(f["id"], {}).items():
        txt = txt.replace(json.dumps(old, ensure_ascii=False), json.dumps(new, ensure_ascii=False))
        txt = txt.replace("$('%s')" % old, "$('%s')" % new)
    f.update(json.loads(txt))
    for n in f["nodes"]:
        if n["name"] in CAPTIONS:
            n["notes"] = CAPTIONS[n["name"]]
            n["notesInFlow"] = True
    f["nodes"] = [sticky(k, pos, w, h, c, t) for k, pos, w, h, c, t in STICKIES.get(f["id"], [])] + f["nodes"]

import re
for f in flows:
    slug = re.sub(r"[^a-z0-9]+", "-", f["name"].lower().replace("ä", "ae").replace("ü", "ue").replace("ö", "oe")).strip("-")
    (OUT / f"{slug}.json").write_text(json.dumps(f, indent=2, ensure_ascii=False) + "\n")
    print(slug)
