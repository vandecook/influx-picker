# Installation und Einstellungen

[English](installation.md) · **Deutsch** · [README](../README.de.md)

Diese Anleitung führt durch Installation und Einrichtung von Influx Picker und
erklärt jede Einstellung. Sie beruht auf einer ersten echten Installation im
Home Assistant des Maintainers (2026-11-23).

> **Frühe Version.** Der Code ist größtenteils KI-generiert und nicht gründlich
> geprüft (siehe [Status-Hinweis](../README.de.md)). Fang mit einem
> **Test-Bucket** an, nicht mit deinen produktiven Daten.

## Inhalt

1. [Voraussetzungen](#1-voraussetzungen)
2. [Installieren](#2-installieren)
3. [Einrichten](#3-einrichten)
4. [Entitäten auswählen](#4-entitäten-auswählen)
5. [Einstellungen später ändern](#5-einstellungen-später-ändern)
6. [Alle Einstellungen](#6-alle-einstellungen)
7. [Umstieg von der nativen `influxdb`-Integration](#7-umstieg-von-der-nativen-influxdb-integration)
8. [Prüfen, ob es funktioniert](#8-prüfen-ob-es-funktioniert)
9. [Fehlersuche](#9-fehlersuche)
10. [Entfernen](#10-entfernen)

## 1. Voraussetzungen

Du brauchst:

- **Home Assistant 2026.10 oder neuer.**
- **HACS** (ab Home Assistant 2026.11: den eingebauten **Marketplace**) oder
  Zugriff auf den Ordner `config` für eine manuelle Installation.
- Einen **InfluxDB®-2.x**-Server. InfluxDB 1.x und 3.x werden noch nicht
  unterstützt.
- In InfluxDB:
  - die **Organisation** (Name oder ID),
  - einen **Bucket** als Ziel (für den ersten Test einen eigenen anlegen, zum
    Beispiel `ha_test`),
  - ein **API-Token mit Schreibrecht** auf diesen Bucket.

Das Token braucht nur Schreibrecht auf diesen einen Bucket. Ein Token mit mehr
Rechten funktioniert auch, ist aber nicht nötig.

## 2. Installieren

### Mit HACS / Marketplace (empfohlen)

1. **HACS** öffnen (oder **Einstellungen → Marketplace**).
2. Menü (drei Punkte oben rechts) → **Benutzerdefinierte Repositories**.
3. Repository `https://github.com/vandecook/influx-picker`, Typ
   **Integration**, dann **Hinzufügen**.
4. Nach **Influx Picker** suchen, öffnen, **Herunterladen**.
5. **Home Assistant neu starten.**

HACS installiert das neueste Release. Updates erscheinen in HACS wie bei jeder
anderen Integration.

### Manuell

1. Repository herunterladen (**Code → Download ZIP**).
2. `custom_components/influx_picker` in den Ordner `custom_components` deiner
   Home-Assistant-Konfiguration kopieren, sodass
   `config/custom_components/influx_picker/manifest.json` existiert.
3. **Home Assistant neu starten.**

## 3. Einrichten

### 3.1 Labels anlegen

Influx Picker schreibt Entitäten, die eines von **zwei Labels** tragen. Leg sie
zuerst an: **Einstellungen → Bereiche, Labels & Zonen → Labels → Label
erstellen**.

| Label (Vorschlag) | Wirkung |
|---|---|
| `influx` | Bei jeder Änderung schreiben. |
| `influx-heartbeat` | Bei jeder Änderung **und** zusätzlich regelmäßig, solange sich nichts ändert (Heartbeat). |

Die Namen sind frei wählbar. Influx Picker speichert die **ID** des Labels,
Umbenennen macht also später nichts kaputt. Du kannst auch nur eines der beiden
Labels verwenden.

### 3.2 Integration hinzufügen

**Einstellungen → Geräte & Dienste → Integration hinzufügen → Influx Picker.**
Die Einrichtung hat vier Schritte.

**Schritt 1: Datenbankversion.** **InfluxDB 2.x** wählen.

**Schritt 2: Verbindung.**

| Feld | Beispiel | Hinweis |
|---|---|---|
| URL | `http://192.168.1.10:8086` | Adresse des InfluxDB-Servers mit Port. |
| Organisation | `home` oder `0123456789abcdef` | Name **oder** ID. Darf das Token keine Organisationen auflisten, die ID verwenden (InfluxDB-Oberfläche → Organisation → About). |
| Bucket | `ha_test` | Muss existieren. |
| API-Token | | Braucht Schreibrecht auf den Bucket. |
| SSL-Zertifikat prüfen | an | Nur bei `https` relevant. Bei selbst signierten Zertifikaten ausschalten. |

Die Verbindung wird mit einer **echten Schreibanfrage** geprüft. Ein falsches
Token, eine falsche Organisation oder ein falscher Bucket fällt also schon hier
auf.

**Schritt 3: Auswahl der Entitäten.** Die beiden Labels, das Heartbeat-Intervall,
ob Labels von Geräten und Bereichen mitzählen und was beim Start geschrieben
wird. Details in
[Abschnitt 6.1](#61-auswahl-der-entitäten).

**Schritt 4: Datenformat.** Legt fest, wie die Punkte in InfluxDB aussehen.

Das Formular ist **vorausgefüllt** mit `default_measurement: units`, dem
festen Tag `source=HA` und `friendly_name` als Tag. Das sind übliche
Einstellungen, **nicht** die nativen Standardwerte (die native Integration lässt
alle drei leer).

- **Neu bei InfluxDB:** die vorausgefüllten Werte lassen oder leeren.
- **Umstieg von der nativen `influxdb`-Integration:** deine YAML-Werte hier
  übernehmen und vorausgefüllte Felder leeren, die nicht in deinem YAML stehen (siehe [Abschnitt 7](#7-umstieg-von-der-nativen-influxdb-integration)).
  **Mach das gleich jetzt**, bevor Daten fließen. Sonst landen die ersten
  Punkte mit den Standardwerten in anderen Measurements als deine bestehenden
  Daten.

## 4. Entitäten auswählen

Häng ein Label an eine **Entität**, ein **Gerät** oder einen **Bereich**:

- **Entität:** Entitätseinstellungen (Zahnrad) → **Labels**.
- **Gerät:** Geräteseite → Stift → **Labels**. Gilt für alle seine Entitäten.
- **Bereich:** Bereichseinstellungen → **Labels**. Gilt für alle Entitäten im
  Bereich (Bereich der Entität, sonst Bereich des Geräts).

Änderungen wirken **nach etwa einer Sekunde, ohne Neustart**. Eine neu
ausgewählte Entität bekommt sofort einen Schreibvorgang mit ihrem aktuellen
Zustand (als Heartbeat markiert, siehe [Abschnitt 6.1](#61-auswahl-der-entitäten)).

**Grenzen:**

- Nur Entitäten mit einer **Unique-ID** können Labels tragen. Manche haben keine
  (zum Beispiel `sun.sun` oder Entitäten aus YAML ohne `unique_id`). Eine
  manuelle Liste dafür ist geplant (Roadmap M3).
- **Deaktivierte** Entitäten werden nicht geschrieben.
- Die Zustände `unknown`, `unavailable` und leere Zustände werden nie
  geschrieben (wie bei der nativen Integration).

## 5. Einstellungen später ändern

**Einstellungen → Geräte & Dienste → Influx Picker → Konfigurieren.** Es öffnet
sich ein Menü:

- **Auswahl der Entitäten:** Labels, Heartbeat-Intervall, Vererbung.
- **Datenformat:** alle Optionen zum Datenformat.

Speichern lädt die Integration neu, ein Neustart von Home Assistant ist nicht
nötig. Nach dem Neuladen bekommt jede ausgewählte Entität wieder einen
Startwert, je nach **Startwert beim Start von Home Assistant** (siehe
[Abschnitt 6.1](#61-auswahl-der-entitäten)).

Die Verbindung (URL, Token, …) lässt sich noch nicht ändern (geplant für M3).
Dafür die Integration entfernen und neu hinzufügen.

## 6. Alle Einstellungen

### 6.1 Auswahl der Entitäten

| Einstellung | Standard | Bedeutung |
|---|---|---|
| Label: bei Änderung schreiben | – | Entitäten mit diesem Label werden bei jeder Zustands- oder Attributänderung geschrieben. |
| Label: bei Änderung und als Heartbeat schreiben | – | Wie oben, plus ein Heartbeat-Schreibvorgang, wenn im Intervall nichts geschrieben wurde. Hat eine Entität beide Labels, gewinnt Heartbeat. |
| Heartbeat-Intervall | 15 min | 1 bis 1440 Minuten. Wird einmal pro Minute geprüft, ein Heartbeat kommt also bis zu einer Minute später. |
| Labels von Gerät und Bereich einbeziehen | an | Aus: nur Labels an der Entität selbst zählen. |
| Startwert beim Start von Home Assistant | Aktuelle Zeit, als Heartbeat markiert | Siehe unten. |

Mindestens ein Label ist nötig. Die beiden Labels müssen verschieden sein.

**Heartbeat- und Startwert-Punkte** tragen ein zusätzliches Feld
`_heartbeat=true`. Änderungspunkte nicht. So markierte Punkte entstehen:

- durch den Heartbeat-Timer,
- einmal für jede Entität, die im laufenden Betrieb neu ausgewählt wird,
- einmal für jede ausgewählte Entität nach dem Start von Home Assistant und nach
  dem Neuladen der Integration (zum Beispiel nach dem Speichern der Optionen),
  außer **Startwert beim Start von Home Assistant** ist anders eingestellt.

Graphen, Mittelwerte und `last()` können alle Punkte verwenden. Abfragen, die
**Änderungen zählen**, müssen Punkte mit `_heartbeat` weglassen; ein
Flux-Beispiel steht unter
[Heartbeat-Markierung](../README.de.md#heartbeat-markierung).

**Startwert beim Start von Home Assistant** legt fest, was beim Start von Home
Assistant oder beim Neuladen der Integration für jede ausgewählte Entität
geschrieben wird:

| Auswahl | Zeitstempel | Markierung | Wofür |
|---|---|---|---|
| Aktuelle Zeit, als Heartbeat markiert (Standard) | jetzt | `_heartbeat=true` | Ein frischer Punkt direkt nach dem Start; verhält sich wie ein Heartbeat. |
| Zeit der letzten Zustandsänderung, mit `_startup` markiert | `last_updated` des Zustands | `_startup=true` | Ergänzt eine Änderung, die rund um einen Neustart verloren ging, zum **richtigen** Zeitpunkt. Gibt es den Punkt schon (gleiche Zeit), wird er mit denselben Werten plus `_startup` überschrieben. |
| Nicht schreiben | – | – | Beim Start nichts. Nur echte Änderungen (und Heartbeats) werden geschrieben. |

Entitäten, die **später** im laufenden Betrieb ausgewählt werden, bekommen immer
den normalen Heartbeat-Startwert. `_startup` ist aus demselben Grund ein Feld
und kein Tag wie `_heartbeat`: Ein Tag würde die Series aufteilen. Ein
`_startup`-Punkt steht meist für eine echte Änderung, beim Zählen von
Änderungen also **nicht** weglassen. Ist der Zustand älter als die
Aufbewahrungsdauer (Retention) des Buckets, lehnt InfluxDB den Punkt ab.

### 6.2 Datenformat

Gleiche Namen, Bedeutung und Standardwerte wie die YAML-Optionen der nativen
`influxdb`-Integration. Bei einer **neuen** Einrichtung sind Standard-Measurement,
feste Tags und Attribute als Tags vorausgefüllt (siehe
[Schritt 4](#32-integration-hinzufügen)); die Spalte "Standard" zeigt den Wert
eines leeren Felds.

| Einstellung | Native YAML-Option | Standard | Bedeutung |
|---|---|---|---|
| Measurement aus | `measurement_attr` | Maßeinheit | Woher der Measurement-Name kommt: die Einheit (`W`, `°C`), `<domain>__<device_class>` (zum Beispiel `sensor__temperature`) oder die Entity-ID. |
| Standard-Measurement | `default_measurement` | leer | Gilt, wenn die Entität für "Measurement aus" keinen Wert hat (zum Beispiel keine Einheit). Leer bedeutet: die volle Entity-ID (`switch.kitchen`). |
| Measurement überschreiben | `override_measurement` | leer | Schreibt **jeden** Punkt in dieses eine Measurement. |
| Feste Tags | `tags` | leer | Ein `Schlüssel=Wert` pro Zeile, zum Beispiel `source=HA`. Kommt an jeden Punkt. |
| Attribute als Tags schreiben | `tags_attributes` | leer | Diese Attribute werden Tags statt Felder, zum Beispiel `friendly_name`. Namen eintippen und Enter drücken. |
| Attribute ignorieren | `ignore_attributes` | leer | Diese Attribute werden nicht geschrieben. |
| Pro Entität | `component_config` | leer | YAML, siehe unten. |
| Pro Domain | `component_config_domain` | leer | YAML, siehe unten. |
| Pro Entitätsmuster | `component_config_glob` | leer | YAML, siehe unten. |

**Pro Entität / Domain / Muster** erwarten eine Zuordnung zu
`override_measurement` und/oder `ignore_attributes`, genau wie im nativen YAML:

```yaml
# Pro Entität
sensor.kitchen_temp:
  override_measurement: temperature
# Pro Domain
light:
  ignore_attributes:
    - effect_list
    - supported_color_modes
# Pro Entitätsmuster
"sensor.*_power":
  override_measurement: power
```

Greifen mehrere, gilt die Reihenfolge Domain, dann Muster, dann Entität (die
genaueste gewinnt), wie bei der nativen Integration.

**So sieht ein Punkt aus** (Standardwerte plus `default_measurement: units`,
`tags: source=HA`, `tags_attributes: friendly_name`):

```text
W,domain=sensor,entity_id=house_total_power,friendly_name=House\ Total\ Power,source=HA device_class_str="power",state_class_str="measurement",value=412 1795448400123456000
units,domain=switch,entity_id=kitchen,friendly_name=Kitchen,source=HA state="on",value=1 1795448400123456000
```

- `value`: der Zustand als Zahl (on/off-artige Zustände als `1`/`0`).
- `state`: der Zustand als Text, bei Zuständen, die keine reinen Zahlen sind.
- Attribute: Zahlen als Feld mit ihrem Namen, Text als `<name>_str`.
- Das Tag `entity_id` ist die Entity-ID **ohne** Domain.

Die vollständigen Regeln stehen in
[docs/core-schema-audit.md](core-schema-audit.md) (englisch).

## 7. Umstieg von der nativen `influxdb`-Integration

Ziel: Die neuen Punkte sehen genauso aus wie die alten, damit Abfragen und
Dashboards weiter funktionieren.

1. Öffne den Abschnitt `influxdb:` deiner `configuration.yaml` (oder die
   eingebundene Datei).
2. Übernimm diese Werte ins **Datenformat** (Einrichtungsschritt 4 oder später
   über **Konfigurieren → Datenformat**):

   | In deinem YAML | Feld in Influx Picker |
   |---|---|
   | `measurement_attr: …` | Measurement aus |
   | `default_measurement: units` | Standard-Measurement: `units` |
   | `override_measurement: …` | Measurement überschreiben |
   | `tags:` `source: HA` | Feste Tags: `source=HA` |
   | `tags_attributes:` `- friendly_name` | Attribute als Tags schreiben: `friendly_name` |
   | `ignore_attributes:` | Attribute ignorieren |
   | `component_config:` | Pro Entität (die Zuordnung unter dem Schlüssel einfügen) |
   | `component_config_domain:` | Pro Domain |
   | `component_config_glob:` | Pro Entitätsmuster |

   Optionen, die nicht in deinem YAML stehen, bleiben leer: Die Standardwerte
   sind dieselben.
3. **Erst testen**, mit einem eigenen Bucket und ein paar Entitäten, und mit
   deinen bestehenden Daten vergleichen ([Abschnitt 8](#8-prüfen-ob-es-funktioniert)).
4. **Doppelte Schreibvorgänge vermeiden:** Solange beide Integrationen
   **dieselben Entitäten** in **denselben Bucket** schreiben, wird jede Änderung
   doppelt geschrieben. Entweder diese Entitäten aus dem `include` der nativen
   Integration nehmen oder einen eigenen Bucket verwenden. Paralleler Betrieb in
   **verschiedene** Buckets ist kein Problem und zum Testen sinnvoll.

## 8. Prüfen, ob es funktioniert

- **In InfluxDB:** Data Explorer → Bucket → Measurement (zum Beispiel `W`) →
  nach `entity_id` filtern. Eine neu ausgewählte Entität erscheint nach wenigen
  Sekunden.
- **Flux, die letzten Punkte einer Entität:**

  ```flux
  from(bucket: "ha_test")
    |> range(start: -15m)
    |> filter(fn: (r) => r.entity_id == "house_total_power" and r._field == "value")
  ```

- **Vergleich mit der nativen Integration** (für Entwickler):
  `tools/compare_with_influx.py` vergleicht für gegebene Zustände die Punkte der
  nativen Integration mit denen, die Influx Picker schreiben würde (nur lesend).
- **Logs:** Einstellungen → System → Protokolle, nach `influx_picker` suchen.
  Schreibfehler werden einmal gemeldet, danach nur noch auf Debug-Ebene, bis
  das Schreiben wieder klappt.

## 9. Fehlersuche

| Problem | Ursache / Lösung |
|---|---|
| Einrichtung: "Das Token ist ungültig oder hat keine Schreibrechte." | Token falsch oder ohne Schreibrecht auf den Bucket. |
| Einrichtung: "Organisation oder Bucket nicht gefunden." | Schreibweise prüfen. Darf das Token keine Organisationen auflisten, die **ID** der Organisation eintragen. |
| Einrichtung: "Keine Verbindung zum Server." | URL und Port prüfen, und ob Home Assistant den Server erreicht. |
| Punkte landen in Measurements mit der Entity-ID als Namen (`switch.kitchen`) | Kein **Standard-Measurement** gesetzt. Beim Umstieg von der nativen Integration `default_measurement` übernehmen ([Abschnitt 7](#7-umstieg-von-der-nativen-influxdb-integration)). |
| `friendly_name` ist ein Feld (`friendly_name_str`) statt eines Tags | `friendly_name` bei **Attribute als Tags schreiben** eintragen. |
| Eine Entität wird nicht geschrieben | Hat sie eine Unique-ID (sonst keine Labels)? Ist sie deaktiviert? Ist ihr Zustand `unknown`/`unavailable`? Hängt das Label an Entität, Gerät oder Bereich, und ist bei Geräte-/Bereichslabels die Vererbung an? |
| Im Optionsformular steht bei einem Label "Unbekanntes Element" | Einmal gesehen, direkt nachdem die Labels bei offener Seite angelegt wurden; der gespeicherte Wert war richtig. Seite neu laden (Strg+F5). Bleibt es, bitte ein Issue öffnen. |
| Jede Änderung erscheint doppelt | Die native Integration schreibt dieselben Entitäten in denselben Bucket ([Abschnitt 7](#7-umstieg-von-der-nativen-influxdb-integration), Schritt 4). |

## 10. Entfernen

1. **Einstellungen → Geräte & Dienste → Influx Picker → ⋮ → Löschen.**
2. In HACS entfernen (oder `custom_components/influx_picker` löschen).
3. Home Assistant neu starten.
4. Die Labels löschen, wenn du sie nicht mehr brauchst. Bereits geschriebene
   Daten bleiben in InfluxDB.

---

InfluxDB® ist eine eingetragene Marke der InfluxData Inc. Dieses Projekt ist
nicht mit InfluxData Inc. verbunden und wird von ihr weder unterstützt noch
gesponsert.
