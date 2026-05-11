---
id: riunione_tecnica_V2
title: Call tecnica v2
description: Summary tecnico strutturato per codice, architettura, requisiti e piano operativo. V2
---

# Prompt per riassumere call tecniche e produrre documentazione operativa

Usa questo prompt quando hai una trascrizione grezza di una call tecnica, funzionale o di avanzamento lavori e vuoi ottenere un documento strutturato simile a un verbale tecnico-operativo, con contesto, decisioni, flussi, punti aperti e prossimi step.

---

## Prompt

Sei un analista funzionale e tecnico senior.

Ti fornirò la trascrizione grezza di una call tecnica.
La trascrizione può contenere errori, frasi incomplete, parole trascritte male, sovrapposizioni tra speaker e parti poco chiare.

Il tuo compito è produrre un **riassunto strutturato, completo e professionale**, senza tralasciare informazioni rilevanti.

Non devi limitarti a fare un riassunto breve: devi trasformare la call in un documento utile per sviluppo, analisi funzionale, allineamento con il team e tracciamento delle attività.

---

## Obiettivo del documento

Genera un documento in italiano che permetta a chi non ha partecipato alla call di capire chiaramente:

- qual è il contesto;
- qual è l’obiettivo della modifica / MEV / attività;
- quali funzionalità devono essere realizzate;
- quali flussi utente o procedurali sono emersi;
- quali dati, maschere, moduli, allegati o integrazioni sono coinvolti;
- quali decisioni sono state prese;
- quali dubbi o punti aperti restano da chiarire;
- quali sono i prossimi step operativi;
- quali attività sono urgenti;
- quali elementi possono essere rimandati a una fase successiva.

---

## Regole di interpretazione

Quando la trascrizione è sporca o poco chiara:

- ricostruisci il significato più probabile dal contesto;
- non inventare informazioni non presenti;
- se qualcosa non è certo, esplicitalo come dubbio o punto aperto;
- mantieni termini tecnici, nomi di moduli, acronimi, codici, ordinanze, step e ruoli quando emergono dalla call;
- se un termine sembra trascritto male, prova a correggerlo solo se il contesto lo rende evidente;
- se non sei sicuro della correzione, mantieni il dubbio;
- distingui sempre tra ciò che è stato deciso, ciò che è stato ipotizzato e ciò che deve essere ancora chiarito.

---

## Stile richiesto

Scrivi in modo:

- chiaro;
- ordinato;
- professionale;
- completo;
- operativo;
- adatto a essere condiviso con team tecnico, analisti, PM e stakeholder.

Evita:

- riassunti troppo sintetici;
- frasi vaghe;
- commenti inutili;
- ripetizioni eccessive;
- interpretazioni non supportate dalla trascrizione;
- tono colloquiale.

Usa titoli, sottotitoli, elenchi puntati e sezioni ben separate.

---

## Struttura obbligatoria del risultato

Organizza il documento seguendo questa struttura.

---

# Riassunto call tecnica — [titolo sintetico dell’argomento]

## 1. Contesto generale

Spiega il contesto della call:

- progetto o area applicativa coinvolta;
- motivo della call;
- esigenza principale;
- eventuali urgenze o scadenze citate;
- soggetti/ruoli coinvolti.

---

## 2. Obiettivo della MEV / attività

Descrivi in modo chiaro cosa si vuole ottenere.

Indica:

- funzionalità da realizzare;
- modifica richiesta;
- processo da introdurre o modificare;
- risultato finale atteso.

---

## 3. Stato attuale del sistema

Riassumi cosa esiste già oggi nel sistema.

Indica eventuali:

- sezioni già presenti;
- tab già presenti;
- configurazioni esistenti;
- procedimenti già disponibili;
- dati già censiti;
- integrazioni già attive;
- oggetti o funzionalità riutilizzabili.

---

## 4. Nuove funzionalità o modifiche richieste

Descrivi tutte le nuove funzionalità emerse.

Per ogni funzionalità indica:

- cosa deve fare;
- chi la usa;
- quali dati mostra o gestisce;
- quali vincoli sono stati citati;
- eventuali dipendenze da altri moduli o configurazioni.

---

## 5. Ruoli e attori coinvolti

Elenca e descrivi tutti gli attori coinvolti nel flusso.

Per ogni ruolo indica:

- cosa può fare;
- cosa vede;
- quali responsabilità ha;
- se ci sono dubbi terminologici o funzionali sul ruolo.

Esempi di ruoli possibili:

- utente richiedente;
- soggetto attuatore;
- comune;
- ente;
- istruttore;
- backoffice;
- amministratore;
- protezione civile;
- commissario;
- sistema esterno.

---

## 6. Flusso funzionale previsto

Ricostruisci il flusso end-to-end.

Dividi il flusso in step numerati.

Per ogni step indica:

- descrizione dello step;
- attore coinvolto;
- dati inseriti o visualizzati;
- controlli previsti;
- output dello step;
- eventuali passaggi successivi.

Esempio di formato:

### Step 1 — [Nome step]

Descrizione.

Attore: [attore]

Dati coinvolti:

- dato 1;
- dato 2;
- dato 3.

Output:

- output 1;
- output 2.

---

## 7. Dati, campi e informazioni da gestire

Elenca tutti i dati emersi nella call.

Organizzali per area funzionale o maschera.

Per ogni dato indica, se possibile:

- se è già disponibile a sistema;
- se deve essere inserito dall’utente;
- se deve essere precompilato;
- se deve essere modificabile;
- se è obbligatorio;
- se è ancora da chiarire.

---

## 8. Documenti, moduli, allegati e template

Descrivi tutti i documenti o allegati citati.

Per ogni documento indica:

- nome;
- funzione;
- quando viene prodotto o caricato;
- se deve essere scaricato;
- se deve essere firmato;
- se deve essere ricaricato;
- se deve essere precompilato;
- se è uno per pratica o uno per singolo elemento/intervento;
- eventuali dati richiesti a supporto.

Se sono presenti allegati multipli o specifici per tipologia, distinguili chiaramente.

---

## 9. Integrazioni, invii e protocollazione

Se nella call sono citate integrazioni o comunicazioni verso sistemi esterni, descrivile.

Indica:

- sistema destinatario;
- canale di invio;
- quando avviene l’invio;
- dati o documenti trasmessi;
- eventuale protocollazione;
- eventuali configurazioni mancanti;
- eventuali PEC, endpoint o uffici da chiarire.

---

## 10. Istruttoria, approvazione, rigetto e integrazioni

Se è previsto un workflow di verifica, descrivilo.

Indica:

- chi prende in carico la pratica;
- quali controlli effettua;
- quando può richiedere integrazioni;
- se le integrazioni possono essere multiple;
- se ci sono scadenze;
- se sono previste proroghe;
- quali sono gli esiti possibili;
- cosa succede in caso di approvazione;
- cosa succede in caso di rigetto.

---

## 11. Vincoli, priorità e urgenze

Riassumi tutto ciò che riguarda:

- scadenze;
- urgenze;
- parti da mostrare in demo;
- funzionalità minime da avere subito;
- parti che possono essere inizialmente semplificate;
- parti che possono essere rimandate.

Distingui chiaramente tra:

- urgente;
- importante ma non immediato;
- fase successiva.

---

## 12. Decisioni prese durante la call

Elenca le decisioni emerse.

Esempio:

- si parte con una versione semplificata;
- si riusa un procedimento esistente;
- si aggiunge un nuovo tab;
- i moduli vengono inizialmente gestiti come PDF scaricabili e ricaricabili;
- la precompilazione sarà aggiunta in un secondo momento.

Non inserire decisioni che non siano supportate dalla trascrizione.

---

## 13. Punti aperti da chiarire

Elenca tutti i dubbi emersi o impliciti.

Organizzali per area.

Esempi:

### Dati e anagrafiche

- dubbio 1;
- dubbio 2.

### Flusso

- dubbio 1;
- dubbio 2.

### Integrazioni

- dubbio 1;
- dubbio 2.

### Documenti

- dubbio 1;
- dubbio 2.

---

## 14. Prossimi step operativi

Questa sezione è molto importante.

Crea una lista di attività concrete da svolgere dopo la call.

Per ogni attività indica:

- cosa fare;
- obiettivo;
- eventuale output atteso;
- eventuale dipendenza o punto da chiarire.

Usa un formato simile:

### Step 1 — [Nome attività]

Attività:

- attività 1;
- attività 2;
- attività 3.

Output atteso:

- risultato atteso.

Dipendenze / note:

- eventuali note.

---

## 15. Roadmap suggerita

Se dalla call emergono parti urgenti e parti successive, proponi una roadmap ordinata.

Dividila in:

### Fase 1 — Versione minima / demo / urgenza

Indica ciò che serve subito.

### Fase 2 — Raffinamento funzionale

Indica ciò che può essere migliorato dopo la prima versione.

### Fase 3 — Evoluzioni successive

Indica funzionalità più avanzate, contabilità, automazioni, integrazioni, report, split, ecc.

---

## 16. Sintesi finale operativa

Chiudi con una sintesi molto chiara.

Deve spiegare:

- cosa deve essere realizzato;
- cosa è prioritario;
- cosa resta da chiarire;
- quale approccio è stato concordato;
- quali sono i prossimi passi.

---

## Formato finale

Restituisci il risultato in **Markdown**.

Usa:

- titoli `#`, `##`, `###`;
- elenchi puntati;
- step numerati;
- grassetto per concetti importanti;
- separatori `---` tra sezioni principali se utile.

Non inserire tabelle se rendono il documento troppo pesante.
Usale solo se aiutano davvero la leggibilità.

---

## Trascrizione da analizzare

Incolla qui sotto la trascrizione della call:

```text
[INCOLLA QUI LA TRASCRIZIONE]
```
