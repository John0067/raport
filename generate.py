#!/usr/bin/env python3
"""Raport zilnic relaxat -> site/index.html

Rulare:  python generate.py            (date reale, ca pe GitHub)
         python generate.py --demo     (date de test, fără internet)
Variabile de mediu (secrete în GitHub):
  ICAL_URLS      adresele secrete iCal din Google Calendar, câte una pe rând
  PAGE_PASSWORD  parola cu care se deschide secțiunea de calendar
"""
import argparse, base64, html, json, os, re, sys, urllib.parse, urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).parent
UA = {"User-Agent": "Mozilla/5.0 (RaportZilnic)"}
STATUS = []  # probleme întâlnite, afișate discret în subsol

ZILE = ["luni", "marți", "miercuri", "joi", "vineri", "sâmbătă", "duminică"]
LUNI = ["ianuarie", "februarie", "martie", "aprilie", "mai", "iunie", "iulie",
        "august", "septembrie", "octombrie", "noiembrie", "decembrie"]
TARI = {"RO": "România", "CZ": "Cehia", "GB": "Marea Britanie", "DE": "Germania",
        "FR": "Franța", "IT": "Italia", "ES": "Spania", "PL": "Polonia",
        "HU": "Ungaria", "AT": "Austria", "BG": "Bulgaria", "GR": "Grecia",
        "SK": "Slovacia", "IE": "Irlanda", "NL": "Olanda", "BE": "Belgia",
        "PT": "Portugalia", "MD": "Moldova", "CH": "Elveția", "SE": "Suedia"}

CITATE = [
    ("Dacă ceva poate merge prost, va merge prost.", "Legea lui Murphy"),
    ("Nimic nu e atât de simplu pe cât pare.", "Legile lui Murphy"),
    ("Orice durează mai mult decât crezi.", "Legile lui Murphy"),
    ("Dacă mai multe lucruri pot merge prost, va merge prost cel care face cele mai mari stricăciuni.", "Legile lui Murphy"),
    ("Orice lucru pe care vrei să-l faci cere mai întâi să faci altceva.", "Legile lui Murphy"),
    ("Lăsate de capul lor, lucrurile tind să meargă de la rău spre mai rău.", "Legile lui Murphy"),
    ("Pâinea prăjită unsă cu unt cade întotdeauna cu partea unsă în jos.", "Legile lui Murphy"),
    ("Coada de alături merge mereu mai repede decât a ta.", "Legile lui Murphy"),
    ("Dacă un experiment merge perfect din prima, ceva nu e în regulă.", "Legea lui Finagle"),
    ("Munca se extinde până umple tot timpul care i-a fost dat.", "Legea lui Parkinson"),
    ("Durează mereu mai mult decât te aștepți, chiar și atunci când ții cont de legea lui Hofstadter.", "Legea lui Hofstadter"),
    ("Nu pune pe seama răutății ceea ce se explică suficient de bine prin prostie.", "Briciul lui Hanlon"),
    ("Într-o ierarhie, fiecare tinde să urce până la nivelul lui de incompetență.", "Principiul lui Peter"),
    ("Când o măsură devine țintă, încetează să mai fie o măsură bună.", "Legea lui Goodhart"),
    ("Adăugarea de oameni la un proiect întârziat îl întârzie și mai mult.", "Legea lui Brooks"),
    ("Nimic nu e construit la timp și în buget.", "Legea lui Cheops"),
    ("Un drum de o mie de mile începe cu un singur pas.", "Lao Tzî"),
    ("Nu contează cât de încet mergi, atâta timp cât nu te oprești.", "Confucius"),
    ("Nu pentru că lucrurile sunt grele nu îndrăznim; pentru că nu îndrăznim, ele sunt grele.", "Seneca"),
    ("Nu există vânt prielnic pentru cine nu știe încotro merge.", "Seneca"),
    ("Imaginația este mai importantă decât cunoașterea.", "Albert Einstein"),
    ("Cel mai bun mod de a prezice viitorul este să-l creezi.", "atribuit lui Peter Drucker"),
    ("Secretul progresului este să începi.", "atribuit lui Mark Twain"),
    ("Excelența nu e un act, ci un obicei.", "Will Durant, despre Aristotel"),
    ("Cine are un «de ce» pentru care să trăiască poate îndura aproape orice «cum».", "Friedrich Nietzsche"),
    ("Singurul lucru pe care îl știu este că nu știu nimic.", "atribuit lui Socrate"),
    ("Orice expert a fost cândva începător.", "Helen Hayes"),
    ("Fii tu însuți; toți ceilalți sunt deja luați.", "atribuit lui Oscar Wilde"),
    ("Cine se scoală de dimineață, departe ajunge.", "proverb românesc"),
    ("Omul sfințește locul.", "proverb românesc"),
    ("Încet-încet, se face drumul.", "vorbă românească"),
    ("Nu lăsa pe mâine ce poți face azi, dar nici nu te grăbi ce poți face frumos.", "vorbă de bun-simț"),
    ("Ai putere asupra minții tale, nu asupra evenimentelor de afară. Înțelege asta și vei găsi liniște.", "Marcus Aurelius"),
    ("Fericirea ține de puterea de a te bucura de lucrurile mici.", "vorbă de seară liniștită"),
]

# ───────────────────────── CITATE NOI ─────────────────────────
# Dimineața: energie, început, curaj, perseverență. Seara: calm, recunoștință, odihnă, răbdare.
# Autor gol ("") = formulare proprie, fără autor. „atribuit lui” = atribuire uzuală, neverificată în sursa primară.

CITATE_NOI_DIMINEATA = [
    # — Seneca
    ("Cât timp amânăm, viața trece pe lângă noi.", "Seneca"),
    ("Suferim mai des în imaginație decât în realitate.", "Seneca"),
    ("Greutățile întăresc mintea, așa cum munca întărește trupul.", "Seneca"),
    ("Nu există drum ușor de pe Pământ spre stele.", "Seneca"),
    ("Nu pentru școală, ci pentru viață învățăm.", "Seneca"),
    ("Nimic nu mi se pare mai nefericit decât omul pe care nu l-a lovit niciodată nenorocul.", "Seneca"),
    ("Norocul vine atunci când pregătirea întâlnește ocazia.", "atribuit lui Seneca"),
    # — Marcus Aurelius
    ("Când ți-e greu să te scoli dimineața, spune-ți: mă trezesc să fac munca unui om.", "Marcus Aurelius"),
    ("Ceea ce stă în calea acțiunii devine acțiune; obstacolul din drum devine drumul.", "Marcus Aurelius"),
    ("Nu mai discuta despre cum ar trebui să fie un om bun. Fii unul.", "Marcus Aurelius"),
    ("Fă fiecare lucru ca și cum ar fi ultimul din viața ta.", "Marcus Aurelius"),
    ("Dacă nu e corect, nu o face; dacă nu e adevărat, nu o spune.", "Marcus Aurelius"),
    ("Viața ta este ceea ce o fac gândurile tale.", "Marcus Aurelius"),
    # — Epictet
    ("Mai întâi spune-ți cine vrei să fii, apoi fă ceea ce trebuie să faci.", "Epictet"),
    ("Nicio mare realizare nu se naște dintr-odată.", "Epictet"),
    ("Cât timp vei mai aștepta ca să ceri mai mult de la tine însuți?", "Epictet"),
    ("Greutățile arată cine suntem cu adevărat.", "Epictet"),
    # — Confucius
    ("A greși și a nu te îndrepta, asta înseamnă cu adevărat a greși.", "Confucius"),
    ("Cine vrea să-și facă bine treaba trebuie mai întâi să-și ascută uneltele.", "Confucius"),
    ("Învață ca și cum nu ai ajunge niciodată la capăt, și ca și cum ți-ar fi teamă să nu pierzi ce ai aflat.", "Confucius"),
    ("Când vezi un om bun, caută să-i semeni; când vezi unul rău, uită-te la tine însuți.", "Confucius"),
    # — Lao Tzî
    ("Cine îi învinge pe alții are forță; cine se învinge pe sine este cu adevărat puternic.", "Lao Tzî"),
    ("Lucrurile mari din lume se fac din lucruri mici.", "Lao Tzî"),
    ("Cine stă pe vârfuri nu rezistă mult în picioare.", "Lao Tzî"),
    # — Antichitate (greacă și latină)
    ("Norocul îi ajută pe cei îndrăzneți.", "Virgiliu"),
    ("Munca stăruitoare învinge totul.", "Virgiliu"),
    ("Timpul zboară și nu se mai întoarce.", "Virgiliu"),
    ("Culege ziua de azi și încrede-te cât mai puțin în mâine.", "Horațiu"),
    ("Cutează să fii înțelept! Începe!", "Horațiu"),
    ("Cine a început a făcut deja jumătate din treabă.", "Horațiu"),
    ("Cât timp respir, sper.", "Cicero"),
    ("Grăbește-te încet.", "Augustus"),
    ("Minte sănătoasă în trup sănătos.", "Juvenal"),
    ("Fiecare om este făuritorul propriului noroc.", "atribuit lui Appius Claudius Caecus"),
    ("Fapte, nu vorbe.", "maximă latină"),
    ("Zeii ne vând toate bunătățile pentru osteneală.", "Epicharm"),
    ("Începutul este cea mai importantă parte a oricărei munci.", "Platon"),
    ("Devino ceea ce ești.", "Pindar"),
    ("Caracterul este destinul omului.", "Heraclit"),
    ("Viața e scurtă, arta e lungă.", "Hipocrate"),
    ("Dați-mi un punct de sprijin și voi mișca Pământul.", "atribuit lui Arhimede"),
    ("Mintea este precursorul tuturor lucrurilor.", "Dhammapada"),
    ("Mintea nu e un vas de umplut, ci o flacără de aprins.", "atribuit lui Plutarh"),
    # — Moderni
    ("Viața e ca mersul pe bicicletă: ca să-ți menții echilibrul, trebuie să mergi înainte.", "Albert Einstein"),
    ("Nu am niciun talent special; sunt doar pasionat de curiozitate.", "Albert Einstein"),
    ("Cine nu a greșit niciodată nu a încercat niciodată ceva nou.", "atribuit lui Albert Einstein"),
    ("Geniul înseamnă un procent de inspirație și nouăzeci și nouă de transpirație.", "Thomas Edison"),
    ("Ai construit castele în aer? Munca nu ți-a fost în zadar; acum pune fundații sub ele.", "Henry David Thoreau"),
    ("Mergi cu încredere în direcția visurilor tale și trăiește viața pe care ți-ai imaginat-o.", "Henry David Thoreau"),
    ("Nimic măreț nu s-a înfăptuit vreodată fără entuziasm.", "Ralph Waldo Emerson"),
    ("A ști nu ajunge; trebuie să aplici. A vrea nu ajunge; trebuie să faci.", "Goethe"),
    ("Ceea ce nu mă omoară mă face mai puternic.", "Friedrich Nietzsche"),
    ("Trebuie să ai haos în tine ca să poți da naștere unei stele dansatoare.", "Friedrich Nietzsche"),
    ("Singurul lucru de care trebuie să ne temem este frica însăși.", "Franklin D. Roosevelt"),
    ("Am aflat că a fi curajos nu înseamnă a nu avea frică, ci a o învinge.", "Nelson Mandela"),
    ("Totul pare imposibil până când se face.", "atribuit lui Nelson Mandela"),
    ("Întunericul nu poate alunga întunericul; doar lumina poate.", "Martin Luther King Jr."),
    ("Trebuie să accepți dezamăgirea finită, dar să nu pierzi niciodată speranța infinită.", "Martin Luther King Jr."),
    ("Viața e fie o aventură îndrăzneață, fie nimic.", "Helen Keller"),
    ("Fă ce poți, cu ce ai, acolo unde ești.", "atribuit lui Theodore Roosevelt"),
    ("Mă pregătesc, iar ocazia mea va veni.", "atribuit lui Abraham Lincoln"),
    ("Nu ceda, nu ceda niciodată.", "Winston Churchill"),
    ("A trăi este lucrul cel mai rar din lume; cei mai mulți doar există.", "Oscar Wilde"),
    ("Curajul înseamnă grație sub presiune.", "Ernest Hemingway"),
    ("Tot ce un om poate închipui, alți oameni pot înfăptui.", "atribuit lui Jules Verne"),
    ("Fierul ruginește când nu e folosit; la fel și mintea fără exercițiu.", "atribuit lui Leonardo da Vinci"),
    ("Cine citește mult și umblă mult vede mult și știe mult.", "Cervantes"),
    ("Nimic nu e mai puternic decât o idee al cărei timp a sosit.", "atribuit lui Victor Hugo"),
    ("Cutează să știi! Folosește-ți propria minte.", "Immanuel Kant"),
    ("Perfectul este dușmanul binelui.", "Voltaire"),
    ("Nu e greu să faci lucrurile; e greu să te pui în starea de a le face.", "atribuit lui Constantin Brâncuși"),
    ("Forța nu vine din puterea trupului, ci dintr-o voință neînfrântă.", "atribuit lui Mahatma Gandhi"),
    ("Nu poți traversa marea doar stând și privind apa.", "atribuit lui Rabindranath Tagore"),
    # — Proverbe
    ("Cade de șapte ori, ridică-te de opt.", "proverb japonez"),
    ("Cel mai bun moment să plantezi un copac a fost acum douăzeci de ani; al doilea cel mai bun este azi.", "proverb"),
    ("Dacă vrei să ajungi repede, mergi singur; dacă vrei să ajungi departe, mergeți împreună.", "proverb african"),
    ("Un singur băț se rupe ușor; un mănunchi, nu.", "proverb"),
    ("Piatra rostogolită nu prinde mușchi.", "proverb"),
    ("Fierul se bate cât e cald.", "proverb românesc"),
    ("Orice început e greu.", "proverb românesc"),
    ("Cine aleargă după doi iepuri nu prinde pe niciunul.", "proverb românesc"),
    ("Cine caută, găsește.", "proverb românesc"),
    ("Unde-i voință, e și putință.", "proverb românesc"),
    ("Nu lăsa pe mâine ce poți face azi.", "proverb românesc"),
    ("Ajută-te și Dumnezeu te va ajuta.", "proverb românesc"),
    ("Cui îi e frică de lup nu merge în pădure.", "proverb românesc"),
    ("Ochii se tem, mâinile lucrează.", "proverb românesc"),
    ("Omul cât trăiește învață.", "proverb românesc"),
    ("Cine întreabă nu greșește.", "proverb românesc"),
    ("Cine are carte, are parte.", "proverb românesc"),
    ("Fă bine și bine vei găsi.", "proverb românesc"),
    ("Cine nu riscă, nu câștigă.", "proverb românesc"),
    # — Gânduri proprii: început
    ("Azi e o pagină albă; scrie-o cum vrei tu.", ""),
    ("Nu trebuie să fie ziua perfectă, ci doar începută.", ""),
    ("Începe de unde ești, cu ce ai, așa cum ești.", ""),
    ("O zi nouă nu cere să fii alt om, ci doar să faci primul pas.", ""),
    ("Astăzi poți face un lucru pe care ieri îl amânai.", ""),
    ("Dimineața nu-ți cere să fii gata, ci să începi.", ""),
    ("Prima oră a zilei dă tonul întregii zile.", ""),
    ("Nu aștepta motivația; începe, și ea vine după tine.", ""),
    ("Cel mai greu e primul minut; restul se face aproape singur.", ""),
    ("O cană caldă, un gând bun și un prim pas mic: ajunge ca să pornești ziua.", ""),
    ("Ziua de azi nu s-a mai întâmplat niciodată; fă-o să conteze.", ""),
    ("Ce faci azi cu mâinile tale hotărăște cum arată mâine.", ""),
    ("Lasă grijile de ieri la ușă și intră ușor în ziua de azi.", ""),
    ("Un început modest bate un plan perfect uitat în sertar.", ""),
    # — pași mici
    ("Pașii mici, făcuți în fiecare zi, ajung mai departe decât salturile rare.", ""),
    ("Nu trebuie să vezi toată scara; urcă doar prima treaptă.", ""),
    ("Fă azi un lucru mic pentru care viitorul tău să-ți mulțumească.", ""),
    ("Un progres mic rămâne tot progres.", ""),
    ("Puțin în fiecare zi ajunge, în timp, la foarte mult.", ""),
    ("Nu te compara cu cei care au pornit înaintea ta; compară-te cu cel de ieri.", ""),
    ("Mai bine un pas mic acum decât un plan mare mâine.", ""),
    ("Dacă un lucru e prea mare, taie-l în bucăți și ia-l pe rând.", ""),
    ("Perseverența nu face zgomot; doar apare în fiecare zi.", ""),
    ("Constanța bate talentul când talentul stă acasă.", ""),
    ("Cine face câte puțin în fiecare zi nu ajunge niciodată la zero.", ""),
    ("Nu ai nevoie de viteză; ai nevoie de direcție și de răbdare.", ""),
    ("Ce începi azi nu trebuie să fie gata azi.", ""),
    ("Terminat e mai bun decât perfect.", ""),
    ("Fă-l mai întâi cum poți, apoi fă-l bine.", ""),
    # — curaj
    ("Teama vine la pachet cu orice lucru care merită făcut.", ""),
    ("Curajul înseamnă să faci primul pas cu mâinile încă tremurând.", ""),
    ("Nu trebuie să nu-ți fie frică; trebuie doar să nu lași frica să conducă.", ""),
    ("Ce te sperie azi poate deveni mâine un lucru de rutină.", ""),
    ("Dacă visul tău nu te sperie puțin, poate e prea mic.", ""),
    ("Încearcă. Cel mai rău e că afli cum se face.", ""),
    ("Greșelile sunt dovada că ai încercat.", ""),
    ("Un eșec e o lecție scumpă, dar cu efect durabil.", ""),
    ("Nu ești obligat să fii bun de la început, ci doar să începi.", ""),
    ("Locul unde te simți nesigur e adesea locul unde crești.", ""),
    ("Cine nu cade niciodată n-a mers niciodată departe.", ""),
    ("Nu-ți fie teamă să pornești încet; teme-te să rămâi pe loc.", ""),
    ("Riscul de a încerca e mai mic decât regretul de a nu fi încercat.", ""),
    ("Curajul de azi devine obișnuința de mâine.", ""),
    ("Nimeni n-a ajuns pe vârf stând jos și așteptând ca muntele să devină mai mic.", ""),
    # — disciplină și atenție
    ("Disciplina e o formă de grijă față de omul care vei fi peste un an.", ""),
    ("Alege un singur lucru important și fă-l bine înaintea tuturor celorlalte.", ""),
    ("Atenția e cea mai prețioasă monedă a zilei; cheltuiește-o cu grijă.", ""),
    ("Un lucru făcut cu toată atenția valorează cât zece făcute pe jumătate.", ""),
    ("Nu orice zgomot merită răspuns; nu orice grabă merită ascultată.", ""),
    ("Spune „da” la puține lucruri, ca să le poți face bine.", ""),
    ("Ordinea din zi începe cu ordinea din minte.", ""),
    ("Zece minute de plan pot câștiga ore întregi.", ""),
    ("Ce nu poți controla lasă; ce poți controla fă.", ""),
    ("O rutină bună e un prieten care nu te dezamăgește.", ""),
    ("Obiceiurile mici construiesc vieți mari.", ""),
    ("Fiecare alegere de azi e un vot pentru omul care vrei să fii.", ""),
    ("Concentrează-te pe ce faci azi; rezultatele vin în urma lui.", ""),
    ("Un obicei bun nu e o pedeapsă, ci o investiție.", ""),
    ("Fă întâi ce trebuie, apoi ce vrei; în ordinea asta ziua e mai ușoară.", ""),
    # — rezistență
    ("Ai trecut deja prin zile grele; ai dovada că poți.", ""),
    ("Furtuna de azi e doar o parte din cer, nu tot cerul.", ""),
    ("Greutatea de azi te face mai tare pentru ce urmează.", ""),
    ("Cine a învățat să se ridice nu se mai teme de cădere.", ""),
    ("Nu trebuie să fii de neînvins; e destul să te ridici încă o dată.", ""),
    ("Fiecare obstacol are un colț pe unde se ocolește sau o treaptă pe care se urcă.", ""),
    ("Oboseala trece, dar ce ai început rămâne.", ""),
    ("Nu renunța în ziua în care e cel mai greu; e ziua în care contează cel mai mult.", ""),
    ("Cine rămâne în picioare după a zecea cădere a învățat ceva ce alții nu vor afla.", ""),
    ("Greul de azi e povestea de mâine.", ""),
    ("Un nor nu înseamnă că soarele a dispărut.", ""),
    ("Ești mai rezistent decât crezi și mai capabil decât ți-a spus ultima zi proastă.", ""),
    ("Nu te opri la prima ușă închisă; mai sunt ferestre.", ""),
    # — învățare
    ("Fiecare zi e o ocazie să afli ceva ce nu știai ieri.", ""),
    ("Cine învață nu îmbătrânește; doar adună ani.", ""),
    ("Curiozitatea e motorul care nu se uzează.", ""),
    ("Întreabă mai mult decât ai crede; răspunsurile scurtează drumul.", ""),
    ("A nu ști încă nu e o rușine; e începutul oricărei învățături.", ""),
    ("Rămâi elev toată viața.", ""),
    ("Orice om pe care îl întâlnești știe ceva ce tu nu știi.", ""),
    ("O carte citită azi poate schimba un an întreg.", ""),
    ("Învață ceva mic în fiecare zi și într-un an vei fi altul.", ""),
    ("Greșelile sunt școala care nu cere taxă, dar cere atenție.", ""),
    # — atitudine și energie
    ("Zâmbetul de dimineață e cea mai ieftină și cea mai bună energie.", ""),
    ("Caută azi ce merge bine; vei găsi mai mult decât crezi.", ""),
    ("Atitudinea nu schimbă ziua, dar schimbă felul în care o trăiești.", ""),
    ("O vorbă bună spusă dimineața se întoarce înmulțită.", ""),
    ("Bucură-te de lucrurile mici; ele sunt, de fapt, cele mari.", ""),
    ("Energia pe care o dai lumii se întoarce la tine cu dobândă.", ""),
    ("Nu poți alege vremea, dar poți alege cum ieși în ea.", ""),
    ("Fii primul care zâmbește în camera în care intri.", ""),
    ("Recunoștința de dimineață face ziua mai ușoară.", ""),
    ("Un strop de aer curat și o hotărâre bună: poți porni.", ""),
    ("Vorbește-ți cum ai vorbi unui prieten drag; ziua o să meargă mai bine.", ""),
    ("Nu toate zilele sunt bune, dar în fiecare există ceva bun.", ""),
    ("Spune-ți azi un lucru frumos despre tine.", ""),
    ("Bunătatea e singura investiție care nu dă niciodată faliment.", ""),
    # — scopuri
    ("Visul fără plan rămâne vis; planul fără primul pas rămâne hârtie.", ""),
    ("Scrie-ți ținta undeva unde o vezi în fiecare zi.", ""),
    ("Un scop clar face drumul mai scurt.", ""),
    ("Nu abandona visul pentru că drumul e lung; drumul e lung pentru toți.", ""),
    ("O țintă mare se atinge prin multe ținte mici.", ""),
    ("Ce îți dorești azi a fost cândva doar o idee.", ""),
    ("Fă-ți timp pentru ce contează, nu doar pentru ce strigă mai tare.", ""),
    ("Cine știe încotro merge găsește mereu un drum.", ""),
    ("Fiecare zi bine folosită e o cărămidă într-o viață bine construită.", ""),
    ("Începe cu sfârșitul în minte: ce vrei să fie adevărat peste un an?", ""),
    # — timp și priorități
    ("Timpul e singura avere pe care o primim în mod egal; folosește-l ca pe una.", ""),
    ("Mâine nu e promis nimănui; azi e al tău.", ""),
    ("Nu căuta timp; fă-ți timp pentru ce contează.", ""),
    ("Ce faci în primele ore ale zilei e darul pe care ți-l faci.", ""),
    ("O oră de lucru concentrat face cât patru de lucru risipit.", ""),
    ("Nu număra zilele; fă zilele să conteze.", ""),
    ("Momentul perfect nu vine; momentul acesta e deja destul de bun.", ""),
    ("Fă azi ce vei vrea să fi făcut peste un an.", ""),
    ("Un minut de curaj poate schimba o zi întreagă.", ""),
    ("Lucrurile importante rar sunt urgente; lucrurile urgente rar sunt importante.", ""),
    # — muncă și meserie
    ("Fă-ți treaba cu grijă chiar dacă nu te vede nimeni; tu o vezi.", ""),
    ("Calitatea e un obicei, nu un accident.", ""),
    ("Meseria bine făcută e o formă de respect față de tine și față de ceilalți.", ""),
    ("Un lucru făcut bine azi îți economisește două mâine.", ""),
    ("Munca făcută cu drag nu obosește la fel.", ""),
    ("Fii mândru de ce construiești, chiar dacă încă nu e terminat.", ""),
    ("Pasiunea te pornește; disciplina te duce până la capăt.", ""),
    ("Talentul deschide ușa; efortul te ține înăuntru.", ""),
    ("Munca de azi e răsplata de mâine.", ""),
    # — diverse
    ("Nu ai nevoie de permisiunea nimănui ca să începi.", ""),
    ("Cea mai bună versiune a ta se construiește zi de zi, nu într-o zi.", ""),
    ("Fii răbdător cu tine și exigent cu pașii tăi.", ""),
    ("Nu uita cât de departe ai ajuns.", ""),
    ("Nimic nu e pierdut cât timp mai poți încerca.", ""),
    ("Ai tot ce-ți trebuie ca să începi; restul afli pe drum.", ""),
    ("Succesul e suma unor eforturi mici, repetate zi de zi.", ""),
    ("Cele mai bune lucruri vin celor care rămân în joc.", ""),
    ("O idee bună fără acțiune e doar o părere.", ""),
    ("Azi e ziua în care îți poți ține promisiunile față de tine.", ""),
]

CITATE_NOI_SEARA = [
    # — Seneca
    ("Nu e sărac cel care are puțin, ci cel care dorește mai mult.", "Seneca"),
    ("Fiecare zi trebuie rânduită ca și cum ar încheia șirul vieții noastre.", "Seneca"),
    ("Cel mai bun leac împotriva mâniei este amânarea.", "Seneca"),
    # — Marcus Aurelius
    ("Nicăieri nu găsește omul un loc mai liniștit decât în propriul suflet.", "Marcus Aurelius"),
    ("Cea mai bună răzbunare este să nu fii ca cel care te-a rănit.", "Marcus Aurelius"),
    ("Ce e bine pentru stup e bine și pentru albină.", "Marcus Aurelius"),
    ("Pierderea nu e altceva decât schimbare.", "Marcus Aurelius"),
    # — Epictet
    ("Nu lucrurile ne tulbură, ci părerile pe care ni le facem despre ele.", "Epictet"),
    ("Nu cere ca lucrurile să se întâmple cum vrei tu; dorește-le așa cum se întâmplă și vei fi liniștit.", "Epictet"),
    ("Înțelept e cel care nu se întristează pentru ce nu are, ci se bucură pentru ce are.", "atribuit lui Epictet"),
    # — Confucius, Lao Tzî
    ("Nu mă întristez că oamenii nu mă cunosc; mă întristez că nu-i cunosc eu pe ei.", "Confucius"),
    ("Tăcerea este un prieten care nu trădează niciodată.", "atribuit lui Confucius"),
    ("Cine știe că are destul este bogat.", "Lao Tzî"),
    ("Cine se cunoaște pe sine este luminat.", "Lao Tzî"),
    ("Cel mai blând lucru din lume înfrânge ce e mai tare.", "Lao Tzî"),
    ("Natura nu se grăbește și totuși totul se împlinește.", "atribuit lui Lao Tzî"),
    # — alți autori
    ("Nimeni nu intră de două ori în aceeași apă.", "Heraclit"),
    ("Viața neexaminată nu merită trăită.", "Socrate"),
    ("Speranța este visul omului treaz.", "atribuit lui Aristotel"),
    ("Cât trăim, să trăim.", "maximă latină"),
    ("Picătura găurește piatra, nu prin forță, ci căzând des.", "Ovidiu"),
    ("Ajunge zilei necazul ei.", "Evanghelia după Matei"),
    ("Toate își au vremea lor, și fiecare lucru de sub cer își are timpul său.", "Ecclesiastul"),
    ("Să ne cultivăm grădina.", "Voltaire"),
    ("Toată nenorocirea oamenilor vine dintr-un singur lucru: că nu știu să stea liniștiți într-o cameră.", "Blaise Pascal"),
    ("Cei mai puternici doi războinici sunt răbdarea și timpul.", "Lev Tolstoi"),
    ("Nu te uita la cuibul de anul trecut; azi nu mai sunt păsări în el.", "Cervantes"),
    ("A te iubi pe tine însuți este începutul unei idile care ține toată viața.", "Oscar Wilde"),
    ("Nimeni nu a sărăcit vreodată dând.", "Anne Frank"),
    ("Nu poți opri valurile, dar poți învăța să navighezi pe ele.", "Jon Kabat-Zinn"),
    ("Mintea e propriul ei loc și poate face un rai din iad și un iad din rai.", "John Milton"),
    ("Fericirea e ca un fluture: cu cât o urmărești, cu atât fuge; dar dacă te așezi liniștit, ți se poate așeza pe umăr.", "Nathaniel Hawthorne"),
    ("Frumusețea va salva lumea.", "Dostoievski, Idiotul"),
    # — proverbe
    ("Dimineața e mai înțeleaptă decât seara.", "proverb românesc"),
    ("Noaptea e cel mai bun sfetnic.", "proverb românesc"),
    ("Răbdarea e mama înțelepciunii.", "proverb românesc"),
    ("Graba strică treaba.", "proverb românesc"),
    ("Apa trece, pietrele rămân.", "proverb românesc"),
    ("Tot răul spre bine.", "proverb românesc"),
    ("Prietenul la nevoie se cunoaște.", "proverb românesc"),
    ("Ce ție nu-ți place, altuia nu face.", "proverb românesc"),
    ("Vorba dulce mult aduce.", "proverb românesc"),
    ("Nu-ți vinde pielea ursului din pădure.", "proverb românesc"),
    ("Haina nu face pe om.", "proverb românesc"),
    ("Nicăieri nu-i ca acasă.", "proverb românesc"),
    ("Nu există vreme proastă, doar haine nepotrivite.", "proverb scandinav"),
    ("Bucuria împărtășită se dublează, durerea împărtășită se înjumătățește.", "proverb suedez"),
    # — gânduri proprii: odihnă
    ("Ai făcut azi tot ce ai putut; e destul.", ""),
    ("Lasă ziua să se încheie; nu e nevoie să o rezolvi toată.", ""),
    ("Odihna nu e un lux, ci o parte din muncă.", ""),
    ("Închide ziua cu un gând bun, nu cu o grijă.", ""),
    ("Ce n-ai terminat azi poate aștepta până mâine; tu ai nevoie de odihnă.", ""),
    ("Seara e momentul în care îți dai voie să încetinești.", ""),
    ("Respiră adânc: ziua a rămas în urmă și ai ieșit întreg din ea.", ""),
    ("Un ceai cald și o seară liniștită repară mai mult decât crezi.", ""),
    ("Unele zile sunt doar zile în care ai ținut piept; și e bine și așa.", ""),
    ("Fii blând cu tine: ai dus azi mai mult decât se vede.", ""),
    ("Nu ți-a ieșit tot azi? Mâine e altă zi și tot tu ești în ea.", ""),
    ("Orice zi se termină, chiar și cea mai grea.", ""),
    ("Liniștea de seară e un dar; primește-l.", ""),
    ("Lasă telefonul deoparte și privește cerul câteva minute.", ""),
    ("O zi bună se numără în clipe, nu în realizări.", ""),
    ("Ce ai greșit azi te învață; ce ai făcut bine te ține în picioare.", ""),
    ("Iartă-te pentru ce nu ai știut încă.", ""),
    ("Un somn bun e cea mai bună pregătire pentru mâine.", ""),
    ("Lasă grijile pe noptieră; dimineața vor fi tot acolo, dar tu vei fi mai odihnit.", ""),
    ("Nu trebuie să câștigi fiecare zi; trebuie doar să treci prin ea cu demnitate.", ""),
    ("Bucuriile mici de seară, o carte, o supă caldă, o voce dragă, țin lumea la locul ei.", ""),
    ("Sună un om drag; o convorbire scurtă poate lumina o seară întreagă.", ""),
    # — recunoștință
    ("Recunoștința transformă ce avem în destul.", ""),
    ("Gândește-te la cineva care te-a ajutat azi, chiar fără să știe.", ""),
    ("Ce ai azi a fost cândva ceea ce îți doreai.", ""),
    ("Numără binecuvântările, nu necazurile; seara se aud mai bine.", ""),
    ("Un acoperiș, o masă caldă și un pat bun sunt mai mult decât au mulți.", ""),
    ("Mulțumirea nu e lipsa dorințelor, ci bucuria de ce există deja.", ""),
    ("Seara e momentul să-ți mulțumești mâinile, picioarele și răbdarea.", ""),
    ("Ce pare obișnuit azi poate fi mâine lucrul pe care ți-l dorești cel mai mult.", ""),
    ("Un cuvânt de mulțumire spus cu voce tare face seara mai caldă.", ""),
    ("Fericirea se ascunde adesea în lucrurile pe care le luăm de la sine înțelese.", ""),
    # — a lăsa în urmă
    ("Ce nu poți schimba, lasă să plece odată cu ziua de azi.", ""),
    ("Nu căra seara greutățile pe care dimineața nu le poți rezolva.", ""),
    ("Nu toate gândurile cer răspuns în seara asta.", ""),
    ("Lasă supărarea la ușă; în pat nu încape.", ""),
    ("Iartă, ca să poți dormi liniștit.", ""),
    ("Ce a fost greu azi nu trebuie să fie greu și mâine.", ""),
    ("Lista de lucruri nefăcute nu dispare dacă o iei cu tine în vis.", ""),
    ("Nu toate bătăliile merită energia ta de seară.", ""),
    ("A lăsa deoparte nu înseamnă a renunța, ci a-ți păstra forțele.", ""),
    ("Un gând negru nu devine adevărat doar pentru că e noapte.", ""),
    ("Nu te certa cu ziua care a trecut; ea nu mai poate răspunde.", ""),
    ("Nu repeta în minte discuții care s-au încheiat.", ""),
    ("Iartă-i pe cei care nu știau mai bine, inclusiv pe tine.", ""),
    ("Ce nu poți controla nu merită să-ți fure somnul.", ""),
    ("Dă drumul zilei cum dai drumul unui porumbel: cu mulțumire.", ""),
    # — reflecție
    ("Seara e ora în care ziua își spune singură lecțiile.", ""),
    ("Întreabă-te: ce m-a bucurat azi? Răspunsul e de obicei mai mare decât crezi.", ""),
    ("Fiecare zi lasă în urmă ceva de învățat și ceva de iubit.", ""),
    ("Privește ziua de azi ca pe o prietenă care pleacă: cu recunoștință.", ""),
    ("Ce ai învățat azi merită scris undeva, fie și într-o frază.", ""),
    ("Cine privește înapoi cu blândețe merge înainte cu încredere.", ""),
    ("Nu toate lecțiile vin cu notă; unele vin cu liniște.", ""),
    ("O seară de reflecție valorează cât o săptămână de grabă.", ""),
    ("Cine își ascultă seara propriile gânduri își cunoaște mai bine drumul.", ""),
    ("Gândește-te la ce ți-a fost bine azi și fă mai mult din asta mâine.", ""),
    # — blândețe față de tine
    ("Nu ești un proiect de terminat, ci un om în curs de devenire.", ""),
    ("Poți fi obosit și, în același timp, destul de bun.", ""),
    ("Vorbește-ți cu aceeași blândețe cu care ai vorbi unui prieten.", ""),
    ("Nu ai de dovedit nimic nimănui în seara asta.", ""),
    ("Ai voie să te odihnești fără să te simți vinovat.", ""),
    ("Greșelile de azi nu te definesc; felul în care te ridici mâine, da.", ""),
    ("Valoarea ta nu se măsoară în bifele de pe listă.", ""),
    ("Ai fost curajos azi în feluri pe care nimeni nu le-a observat.", ""),
    ("Nu ești în urmă; ești pe drumul tău.", ""),
    ("Oprește-te puțin: ai ajuns mai departe decât crezi.", ""),
    ("Rămâi blând cu tine; nu ești dușmanul tău.", ""),
    ("A fi imperfect e singurul mod de a fi om.", ""),
    ("Mai e timp; nu s-a terminat nimic ce nu poate începe din nou.", ""),
    ("Un om obosit nu e un om slab; e un om care a încercat.", ""),
    ("Ai dreptul să fii mulțumit și când ai făcut doar destul.", ""),
    # — răbdare
    ("Lucrurile bune cresc în tăcere, ca semințele sub pământ.", ""),
    ("Răbdarea nu înseamnă să aștepți, ci să rămâi liniștit cât lucrezi.", ""),
    ("Nu poți grăbi o floare, dar poți uda grădina în fiecare zi.", ""),
    ("Tot ce a fost durabil s-a construit încet.", ""),
    ("Dă-ți timp; ai nevoie de el ca orice lucru bun.", ""),
    ("Vindecarea nu are termen limită.", ""),
    ("Nu toate răspunsurile vin repede; unele vin în somn.", ""),
    ("Cu cât ești mai răbdător, cu atât drumul pare mai scurt.", ""),
    ("Mâine ai o nouă șansă; azi n-a fost ultima.", ""),
    ("Un pas întârziat e tot un pas.", ""),
    # — liniște și natură
    ("Cerul de seară ne amintește că și lumina știe să plece frumos.", ""),
    ("Liniștea nu e absența zgomotului, ci prezența păcii din tine.", ""),
    ("O plimbare lentă înainte de culcare face cât un sfat bun.", ""),
    ("Când afară se întunecă, înăuntru poți aprinde o lumină mică.", ""),
    ("Noaptea are propria ei înțelepciune; ascult-o.", ""),
    ("Stelele sunt acolo și ziua; noaptea doar le dă voie să se vadă.", ""),
    ("Adu-ți aminte de un loc în care te-ai simțit în pace și mergi acolo cu gândul.", ""),
    ("Respiră: inspiră liniște, expiră grija.", ""),
    ("O seară fără grabă e o seară câștigată.", ""),
    ("Vântul care bate azi se potolește mâine.", ""),
    ("Un foc mic, o pătură și puțină tăcere: o seară completă.", ""),
    ("Lumina lunii nu face zgomot și totuși se vede de departe.", ""),
    ("Ploaia de seară spală praful zilei.", ""),
    ("Gândul bun de dinaintea somnului lucrează toată noaptea.", ""),
    ("Lasă mintea să stea ca un lac în amurg: limpede, fără valuri.", ""),
    # — oameni
    ("Cei dragi sunt cea mai bună odihnă.", ""),
    ("Un om care te ascultă e o odihnă mai bună decât un pat.", ""),
    ("Spune-i cuiva seara că ții la el; ziua următoare începe mai bine pentru amândoi.", ""),
    ("Nu amâna îmbrățișarea pe care o poți da azi.", ""),
    ("Prietenii adevărați nu se numără, se simt.", ""),
    ("O masă la care râd oamenii valorează mai mult decât un banchet tăcut.", ""),
    ("Ce dai din inimă nu se pierde.", ""),
    ("A fi acasă e un sentiment, nu doar un loc.", ""),
    ("Cine are pe cineva cu care să tacă împreună nu e singur.", ""),
    ("Uneori cea mai bună conversație e cea fără cuvinte, în aceeași cameră.", ""),
    # — speranță și mâine
    ("Mâine e o pagină nescrisă; azi poți să-ți pregătești stiloul.", ""),
    ("Orice noapte se termină cu o dimineață.", ""),
    ("Planul de mâine poate fi scris în trei rânduri și lăsat deoparte.", ""),
    ("Mâine ai ocazia să faci un lucru mai bine decât azi.", ""),
    ("Speranța e ceea ce rămâne aprins când restul se stinge.", ""),
    ("Nu știm ce aduce mâine, dar știm că vom fi acolo să-l primim.", ""),
    ("Să adormi cu o intenție bună înseamnă să te trezești cu o direcție.", ""),
    ("După fiecare întuneric vine o lumină, chiar dacă nu pare aproape.", ""),
    ("Ziua de mâine nu te așteaptă perfect, ci doar prezent.", ""),
    ("Fă-ți seara un gând frumos despre dimineață.", ""),
    # — bucurii simple
    ("O carte bună e o călătorie făcută fără să ieși din casă.", ""),
    ("Un duș cald, haine curate și liniște: mici lucruri mari.", ""),
    ("Muzica potrivită face o seară din orice moment.", ""),
    ("Supa caldă e un fel de îmbrățișare servită în farfurie.", ""),
    ("O pisică pe canapea știe mai bine decât noi cum se odihnește.", ""),
    ("Dacă a gătit cineva pentru tine, mulțumește; e o formă de iubire.", ""),
    ("Un film vechi, o pătură și un gând liniștit.", ""),
    ("Un geam deschis, aer proaspăt și cinci minute de nimic.", ""),
    ("Gustul unei mere coapte sau al unui ceai cald e o mică vacanță.", ""),
    ("O seară bună nu cere mult: lumină blândă, un om drag, liniște.", ""),
    # — perspectivă
    ("Viața nu e o cursă, ci o plimbare; uneori e bine să te așezi pe o bancă.", ""),
    ("Cele mai importante lucruri nu se văd pe o listă de sarcini.", ""),
    ("Ziua trece, omul rămâne; ai grijă de omul care ești.", ""),
    ("Nu toate zilele trebuie să fie memorabile; unele trebuie doar să fie liniștite.", ""),
    ("Cine nu are timp de odihnă va avea mai târziu timp de boală.", ""),
    ("Echilibrul nu e o stare, e o alegere repetată.", ""),
    ("Cine știe să se oprească ajunge mai departe decât cine nu se oprește niciodată.", ""),
    ("Fericirea nu stă în ce lipsește, ci în ce e deja aici.", ""),
    ("Viața se țese din zile obișnuite trăite cu inimă.", ""),
    ("Cel mai prețios lucru pe care îl ai e atenția; seara, oferă-o celor dragi.", ""),
    # — somn și sănătate
    ("Somnul nu e timp pierdut, e timp investit.", ""),
    ("Corpul tău te-a purtat toată ziua; mulțumește-i cu o noapte bună.", ""),
    ("Nicio problemă nu s-a rezolvat vreodată mai bine la ora trei dimineața.", ""),
    ("Un trup odihnit gândește mai limpede decât unul epuizat.", ""),
    ("Închide ochii: ziua și-a făcut treaba, acum e rândul tău să te odihnești.", ""),
    ("Lasă ecranele deoparte și ia liniștea; ochii tăi îți vor mulțumi.", ""),
    ("O mică întindere, un pahar cu apă și gata: ești pregătit pentru somn.", ""),
    ("Sănătatea se construiește și din nopțile bune.", ""),
    ("Nu e slăbiciune să te culci devreme; e înțelepciune.", ""),
    ("O seară bună e începutul unei dimineți bune.", ""),
    # — felurite
    ("Dacă azi ai făcut doar jumătate din ce-ți propuseși, ai făcut mai mult decât dacă nu încercai.", ""),
    ("Lista de mâine poate aștepta până mâine; asta e și rostul ei.", ""),
    ("Nu ești leneș; ești om.", ""),
    ("Unele zile sunt pentru realizări, altele pentru recuperare; amândouă sunt necesare.", ""),
    ("Dacă ai ajuns până aici, ai trecut deja prin cea mai grea parte a zilei.", ""),
    ("Cafeaua de mâine te așteaptă; tu odihnește-te acum.", ""),
    ("Un om care se oprește la timp ajunge întreg la destinație.", ""),
    ("Lumea se va învârti și fără tine câteva ore; încearcă.", ""),
    ("Mulțumește-ți că ai continuat, chiar și când ai fi vrut să te oprești.", ""),
    ("Orice zi cu un moment de râs e o zi bună.", ""),
    ("Seara, bucură-te că ai ajuns; dimineața, că poți începe din nou.", ""),
    ("Cele mai bune idei vin deseori după ce te-ai odihnit.", ""),
    ("Păstrează în minte un lucru frumos din zi; lasă restul să se așeze.", ""),
    ("Prețuiește oamenii care îți fac seara mai ușoară.", ""),
    ("Nu ai nevoie de o zi extraordinară ca să ai o viață bună.", ""),
    ("Nu te grăbi spre mâine; mai ai ceva de trăit în seara asta.", ""),
    ("Fiecare apus ne amintește că orice se încheie frumos poate reîncepe.", ""),
    ("Puțină tăcere, puțină lumină și un gând blând fac seara bună.", ""),
    ("Un om mulțumit nu e cel care are tot, ci cel care știe să se oprească.", ""),
    # — completări
    ("Ziua care s-a încheiat nu-ți mai datorează nimic; mâine e o socoteală nouă.", ""),
    ("Nu toate gândurile merită să te urmeze în pat.", ""),
    ("Un gând recunoscător înainte de somn e cea mai simplă rugăciune.", ""),
    ("Seara spune-ți: am făcut ce am putut cu ce am avut.", ""),
    ("Pacea nu vine când totul e rezolvat, ci când accepți ce nu poate fi rezolvat azi.", ""),
    ("Nu trebuie să ai toate răspunsurile ca să dormi bine.", ""),
    ("Fiecare seară liniștită e o mică victorie asupra grabei.", ""),
    ("Cu o respirație lungă, ziua se așază la locul ei.", ""),
    ("Ce ai semănat azi va crește fără să te uiți la el toată noaptea.", ""),
    ("Un om care știe să mulțumească nu e niciodată cu totul sărac.", ""),
    ("Lumina caldă a unei lămpi poate face dintr-o cameră obișnuită un adăpost.", ""),
    ("Seara e pentru ce te hrănește, nu pentru ce te grăbește.", ""),
    ("Oprește-te acolo unde ești: ai ajuns destul de departe pentru azi.", ""),
    ("Așază-ți gândurile ca pe haine: frumos, pentru a doua zi.", ""),
    ("Somn ușor și gânduri blânde.", ""),
    ("O seară în care nu ai nimic de dovedit e o seară câștigată.", ""),
]


# Autori de „legi” hazlii: rămân în pool-ul de seară (relaxare); restul vechilor citate merg dimineața.
_AUTORI_SEARA = {"Legea lui Murphy", "Legile lui Murphy", "Legea lui Finagle", "Legea lui Parkinson",
                 "Legea lui Hofstadter", "Briciul lui Hanlon", "Principiul lui Peter", "Legea lui Goodhart",
                 "Legea lui Brooks", "Legea lui Cheops", "vorbă de seară liniștită"}


def alege_citat(edition, today):
    """Un citat pe ediție; dimineața și seara au liste diferite. Ordinea e amestecată (fix), fără repetări
    până se termină lista."""
    import random
    if edition == "morning":
        pool = [q for q in CITATE if q[1] not in _AUTORI_SEARA] + CITATE_NOI_DIMINEATA
    else:
        pool = [q for q in CITATE if q[1] in _AUTORI_SEARA] + CITATE_NOI_SEARA
    seen, uniq = set(), []
    for q in pool:
        if q[0] not in seen:
            seen.add(q[0])
            uniq.append(q)
    order = list(range(len(uniq)))
    random.Random(2026).shuffle(order)
    return uniq[order[today.toordinal() % len(uniq)]]


WMO = {
    0: ("☀️", "Senin"), 1: ("🌤️", "Mai mult senin"), 2: ("⛅", "Parțial noros"),
    3: ("☁️", "Noros"), 45: ("🌫️", "Ceață"), 48: ("🌫️", "Ceață cu chiciură"),
    51: ("🌦️", "Burniță"), 53: ("🌦️", "Burniță"), 55: ("🌧️", "Burniță deasă"),
    56: ("🌧️", "Burniță înghețată"), 57: ("🌧️", "Burniță înghețată"),
    61: ("🌧️", "Ploaie ușoară"), 63: ("🌧️", "Ploaie"), 65: ("🌧️", "Ploaie puternică"),
    66: ("🌧️", "Ploaie înghețată"), 67: ("🌧️", "Ploaie înghețată"),
    71: ("🌨️", "Ninsoare ușoară"), 73: ("🌨️", "Ninsoare"), 75: ("❄️", "Ninsoare puternică"),
    77: ("🌨️", "Fulgi"), 80: ("🌦️", "Averse"), 81: ("🌧️", "Averse"),
    82: ("⛈️", "Averse puternice"), 85: ("🌨️", "Averse de ninsoare"),
    86: ("❄️", "Averse de ninsoare"), 95: ("⛈️", "Furtună"),
    96: ("⛈️", "Furtună cu grindină"), 99: ("⛈️", "Furtună cu grindină"),
}

# Plasă de siguranță dacă sursa online pentru sărbători nu răspunde (sărbători mari, date fixe)
SARBATORI_FIXE = {
    "01-01": "Anul Nou · Sf. Vasile cel Mare (ortodox) · Sfânta Maria, Maica lui Dumnezeu (catolic)",
    "01-06": "Botezul Domnului – Boboteaza (ortodox) · Epifania (catolic)",
    "01-07": "Soborul Sf. Ioan Botezătorul (ortodox)",
    "02-02": "Întâmpinarea Domnului (ortodox) · Prezentarea Domnului (catolic)",
    "03-25": "Buna Vestire / Bunavestire (ortodox și catolic)",
    "04-23": "Sf. Gheorghe",
    "05-21": "Sf. Constantin și Elena",
    "06-24": "Nașterea Sf. Ioan Botezătorul",
    "06-29": "Sf. Apostoli Petru și Pavel",
    "07-20": "Sf. Ilie",
    "08-06": "Schimbarea la Față",
    "08-15": "Adormirea Maicii Domnului (ortodox) · Asumpțiunea (catolic)",
    "08-29": "Tăierea capului Sf. Ioan Botezătorul",
    "09-08": "Nașterea Maicii Domnului",
    "09-14": "Înălțarea Sfintei Cruci",
    "10-14": "Sf. Cuvioasă Parascheva",
    "10-26": "Sf. Dimitrie",
    "11-01": "Toți Sfinții (catolic)",
    "11-08": "Sf. Arhangheli Mihail și Gavriil",
    "11-21": "Intrarea în biserică a Maicii Domnului",
    "11-25": "Sf. Ecaterina",
    "11-30": "Sf. Apostol Andrei",
    "12-06": "Sf. Nicolae",
    "12-08": "Nemaculata Zămislire (catolic)",
    "12-25": "Nașterea Domnului – Crăciunul",
    "12-26": "Soborul Maicii Domnului",
    "12-27": "Sf. Ștefan",
}


def esc(s):
    return html.escape(str(s), quote=True)


def http_get(url, timeout=20):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def get_json(url):
    return json.loads(http_get(url).decode("utf-8"))


def warn(what, err):
    STATUS.append(f"{what}: {str(err)[:90]}")
    print(f"[!] {what}: {err}", file=sys.stderr)


def flag(cc):
    cc = "GB" if cc == "UK" else cc
    return "".join(chr(0x1F1E6 + ord(c) - 65) for c in cc.upper())


def soft_error(what):
    return f'<p class="muted">N-am reușit să încarc „{esc(what)}” acum 🙈 Mai încerc la următoarea rulare.</p>'


# ───────────────────────── VREME ─────────────────────────

def fetch_weather(loc):
    q = {
        "latitude": loc["lat"], "longitude": loc["lon"], "timezone": "auto", "forecast_days": 5,
        "current": "temperature_2m,apparent_temperature,weather_code,wind_speed_10m,relative_humidity_2m",
        "daily": ("weather_code,temperature_2m_max,temperature_2m_min,apparent_temperature_max,"
                  "apparent_temperature_min,precipitation_probability_max,precipitation_sum,"
                  "wind_speed_10m_max,uv_index_max,sunrise,sunset"),
    }
    d = get_json("https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode(q))
    c, dd = d["current"], d["daily"]
    days = []
    for i in range(len(dd["time"])):
        days.append({
            "date": dd["time"][i], "code": dd["weather_code"][i],
            "tmax": dd["temperature_2m_max"][i], "tmin": dd["temperature_2m_min"][i],
            "fmax": dd["apparent_temperature_max"][i], "fmin": dd["apparent_temperature_min"][i],
            "pop": dd["precipitation_probability_max"][i] or 0,
            "precip": dd["precipitation_sum"][i] or 0,
            "wind": dd["wind_speed_10m_max"][i] or 0, "uv": dd["uv_index_max"][i] or 0,
            "sunrise": dd["sunrise"][i], "sunset": dd["sunset"][i],
        })
    return {"loc": loc, "cur": {"temp": c["temperature_2m"], "feels": c["apparent_temperature"],
                                "code": c["weather_code"], "wind": c["wind_speed_10m"],
                                "hum": c["relative_humidity_2m"]}, "days": days}


def clothing(day):
    """Reguli simple, pe înțelesul tuturor."""
    t = (day["fmax"] + day["fmin"]) / 2
    if t <= -5:
        base = [("🧥", "Geacă groasă de iarnă, căciulă, mănuși și fular"),
                ("🥾", "Ghete călduroase, cu talpă bună"), ("🧦", "Șosete groase – degetele îți vor mulțumi")]
    elif t <= 2:
        base = [("🧥", "Geacă de iarnă, căciulă și mănuși"), ("🧣", "Fularul nu strică"),
                ("🥾", "Încălțăminte călduroasă")]
    elif t <= 8:
        base = [("🧥", "Geacă călduroasă sau palton"), ("🧶", "Pulover gros, pantaloni lungi"),
                ("🧣", "Un fular ușor")]
    elif t <= 13:
        base = [("🧥", "Jachetă sau geacă de tranziție"), ("👕", "Pulover peste tricou")]
    elif t <= 18:
        base = [("🧶", "Hanorac sau cardigan"), ("👖", "Pantaloni lungi")]
    elif t <= 23:
        base = [("👕", "Tricou, plus ceva ușor pentru seară")]
    elif t <= 28:
        base = [("👕", "Haine ușoare, respirabile"), ("🧢", "Pălărie sau șapcă")]
    else:
        base = [("🩳", "Cât mai ușor și cât mai puțin"), ("💧", "Apă la tine, umbră la prânz")]
    code = day["code"]
    snow = code in (71, 73, 75, 77, 85, 86)
    if snow:
        base.append(("🥾", "Bocanci – pe jos poate fi alunecos"))
    elif day["pop"] >= 50 or code in (61, 63, 65, 66, 67, 80, 81, 82, 95, 96, 99):
        base.append(("☂️", f"Umbrelă sau geacă impermeabilă (șanse de ploaie {day['pop']}%)"))
    elif day["pop"] >= 30:
        base.append(("☂️", "O umbrelă mică în geantă, just in case"))
    if day["wind"] >= 30:
        base.append(("🌬️", f"Vânt serios (până la {day['wind']:.0f} km/h) – ceva care oprește vântul"))
    if day["fmax"] - day["fmin"] >= 10:
        base.append(("🧅", "Diferență mare între dimineață și prânz – îmbracă-te în straturi"))
    if day["uv"] >= 6:
        base.append(("😎", "UV ridicat – ochelari și cremă"))
    if code in (45, 48):
        base.append(("🚗", "Ceață – dacă mergi cu mașina, mai ușor pe accelerator"))
    return base


def hhmm(iso):
    return iso[11:16] if iso and len(iso) >= 16 else "–"


SCURT = ["Lun", "Mar", "Mie", "Joi", "Vin", "Sâm", "Dum"]


def moon_info(d):
    """Faza Lunii calculată local (aproximativ, ±câteva ore)."""
    import math
    from datetime import timezone
    ref = datetime(2000, 1, 6, 18, 14, tzinfo=timezone.utc)
    now = datetime(d.year, d.month, d.day, 12, tzinfo=timezone.utc)
    syn = 29.530588853
    age = ((now - ref).total_seconds() / 86400) % syn
    illum = (1 - math.cos(2 * math.pi * age / syn)) / 2 * 100
    phases = [(1.85, "🌑", "Lună nouă"), (5.54, "🌒", "Semilună crescătoare"), (9.23, "🌓", "Primul pătrar"),
              (12.92, "🌔", "Lună crescătoare"), (16.61, "🌕", "Lună plină"), (20.3, "🌖", "Lună descrescătoare"),
              (23.99, "🌗", "Ultimul pătrar"), (27.68, "🌘", "Semilună descrescătoare"), (99, "🌑", "Lună nouă")]
    em, name = next((e, n) for lim, e, n in phases if age < lim)
    to_new = syn - age
    to_full = (syn / 2 - age) if age < syn / 2 else (syn * 1.5 - age)
    return {"emoji": em, "name": name, "illum": illum, "new": d + timedelta(days=round(to_new)),
            "full": d + timedelta(days=round(to_full))}


def day_length(sr, ss):
    try:
        a = datetime.fromisoformat(sr); b = datetime.fromisoformat(ss)
        m = int((b - a).total_seconds() // 60)
        return f"{m // 60} h {m % 60:02d} min"
    except Exception:
        return "–"


def short_date(d):
    return f"{d.day} {LUNI[d.month - 1][:3]}."


def render_location_card(w, edition, show_clothing, today):
    loc, cur, days = w["loc"], w["cur"], w["days"]
    t0 = days[0]
    e, txt = WMO.get(cur["code"], ("🌡️", ""))
    idx = 1 if edition == "evening" and len(days) > 1 else 0
    tgt = days[idx]
    moon = moon_info(today)
    p = [f'<h2>{esc(loc.get("emoji", "📍"))} {esc(loc["name"])}</h2>',
         f'<div class="now"><span class="big">{e} {cur["temp"]:.0f}°</span>'
         f'<span class="desc">{esc(txt)} · se simte ca {cur["feels"]:.0f}°</span></div>',
         '<div class="chips">'
         f'<span>🌡️ azi {t0["tmin"]:.0f}° / {t0["tmax"]:.0f}°</span><span>☔ {t0["pop"]:.0f}%</span>'
         f'<span>💨 {cur["wind"]:.0f} km/h</span><span>💧 {cur["hum"]:.0f}%</span></div>',
         '<h3>🌅 Soare și Lună</h3><div class="chips">'
         f'<span>🌅 răsărit {hhmm(t0["sunrise"])}</span><span>🌇 apus {hhmm(t0["sunset"])}</span>'
         f'<span>⏳ zi de {day_length(t0["sunrise"], t0["sunset"])}</span>'
         f'<span>{moon["emoji"]} {esc(moon["name"])} · {moon["illum"]:.0f}% luminată</span></div>'
         f'<p class="muted tiny">Următoarea lună plină: ~{short_date(moon["full"])} · lună nouă: ~{short_date(moon["new"])}</p>',
         f'<h3>📅 Următoarele {len(days)} zile</h3><div class="fc">']
    for i, d in enumerate(days):
        dd = date.fromisoformat(d["date"])
        label = "Azi" if i == 0 else "Mâine" if i == 1 else f"{SCURT[dd.weekday()]} {dd.day}"
        ee, tt = WMO.get(d["code"], ("🌡️", ""))
        p.append(f'<div class="fcrow"><span class="fd">{label}</span><span class="fi" title="{esc(tt)}">{ee}</span>'
                 f'<span class="ft"><b>{d["tmax"]:.0f}°</b> zi · {d["tmin"]:.0f}° noapte</span>'
                 f'<span class="fp">☔ {d["pop"]:.0f}%</span></div>')
    p.append("</div>")
    if show_clothing:
        title = "Ce îmbraci mâine" if idx == 1 else "Ce îmbraci azi"
        p.append(f'<h3>🧥 {title}</h3><ul class="dress">')
        for em, t in clothing(tgt):
            p.append(f"<li><span>{em}</span> {esc(t)}</li>")
        p.append("</ul>")
    return "".join(p)


def render_weather(wlist, edition, show_clothing, today, panels):
    """Panouri cu listă de locații: cardurile sunt toate în pagină, alegerea se face din meniu."""
    cards = [render_location_card(w, edition, show_clothing, today) for w in wlist]
    names = [w["loc"]["name"] for w in wlist]
    opts_all = [f'{w["loc"].get("emoji", "📍")} {w["loc"]["name"]}' for w in wlist]
    defaults = []
    for i, pn in enumerate(panels or names[:2]):
        defaults.append(names.index(pn) if pn in names else min(i, len(names) - 1))
    out = ['<div class="grid two">']
    for pi, di in enumerate(defaults):
        opts = "".join(f'<option value="{esc(n)}"{" selected" if k == di else ""}>{esc(o)}</option>'
                       for k, (n, o) in enumerate(zip(names, opts_all)))
        out.append(f'<div class="card panel" data-panel="{pi}"><div class="pick"><label>Locație: '
                   f'<select>{opts}</select></label></div><div class="panel-body">{cards[di]}</div></div>')
    out.append("</div>")
    out.append('<div id="wx-store" hidden>' + "".join(
        f'<div data-loc="{esc(n)}">{c}</div>' for n, c in zip(names, cards)) + "</div>")
    return "".join(out)


# ───────────────────────── CALENDAR (criptat) ─────────────────────────

def fetch_calendar_events(urls, tz, days_dates):
    import icalendar, recurring_ical_events
    result = {d: [] for d in days_dates}
    for url in urls:
        try:
            cal = icalendar.Calendar.from_ical(http_get(url, 30))
            q = recurring_ical_events.of(cal)
            cname = str(cal.get("X-WR-CALNAME", "") or "")
            for d in days_dates:
                for ev in q.at(d):
                    s = ev.get("DTSTART").dt
                    allday = not isinstance(s, datetime)
                    if not allday:
                        s = s.astimezone(tz) if s.tzinfo else s
                    result[d].append({
                        "time": None if allday else s.strftime("%H:%M"),
                        "title": str(ev.get("SUMMARY", "(fără titlu)")),
                        "where": str(ev.get("LOCATION", "") or ""), "cal": cname,
                    })
        except Exception as e:
            warn("calendar", e)
    for d in result:
        result[d].sort(key=lambda x: (x["time"] is not None, x["time"] or ""))
    return result


def render_calendar_inner(events, today):
    parts = []
    for d, label in ((today, "Azi"), (today + timedelta(days=1), "Mâine")):
        evs = events.get(d, [])
        parts.append(f"<h3>🗓️ {label}</h3>")
        if not evs:
            parts.append('<p class="muted">Nimic în calendar. Zi liberă pentru ce vrei tu 🍃</p>')
            continue
        parts.append('<ul class="events">')
        for ev in evs:
            when = ev["time"] or "toată ziua"
            place = f' <span class="muted">· 📍 {esc(ev["where"])}</span>' if ev["where"] else ""
            parts.append(f'<li><b>{esc(when)}</b> {esc(ev["title"])}{place}</li>')
        parts.append("</ul>")
    return "".join(parts)


def encrypt_block(plain_html, password):
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    salt, iv, iters = os.urandom(16), os.urandom(12), 200000
    key = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=iters).derive(password.encode())
    ct = AESGCM(key).encrypt(iv, plain_html.encode("utf-8"), None)
    b = lambda x: base64.b64encode(x).decode()
    return {"salt": b(salt), "iv": b(iv), "ct": b(ct), "iter": iters}


def render_calendar(events, today, password, demo):
    inner = render_calendar_inner(events, today)
    enc = encrypt_block(inner, password)
    hint = ' <span class="muted">(demo: parola este <b>demo</b>)</span>' if demo else ""
    return (
        '<div class="card"><h2>🗓️ Calendarul tău</h2>'
        f'<div id="cal-lock" data-enc=\'{json.dumps(enc)}\'>'
        '<p class="muted">Conținut protejat 🔒 Introdu parola o singură dată – o țin minte pe acest dispozitiv.' + hint + '</p>'
        '<form id="cal-form"><input id="cal-pw" type="password" placeholder="parola" autocomplete="current-password">'
        '<button type="submit">Deschide</button></form><p id="cal-err" class="muted"></p></div>'
        '<div id="cal-open" hidden></div></div>'
    )


# ───────────────────────── SĂRBĂTORI ─────────────────────────

def clean_wiki(s):
    s = re.sub(r"<ref[^>]*?/>|<ref[^>]*?>.*?</ref>", "", s, flags=re.S)
    s = re.sub(r"<!--.*?-->", "", s, flags=re.S)
    s = re.sub(r"\{\{(?:nowrap|nobr|lang\|[a-z-]+)\|([^{}|]*)\}\}", r"\1", s, flags=re.I)
    for _ in range(4):
        s = re.sub(r"\{\{[^{}]*\}\}", "", s)
    s = re.sub(r"\[\[(?:Fișier|File|Imagine|Categorie|Category):[^\]]*\]\]", "", s)
    s = re.sub(r"\[\[[^\]|]*\|([^\]]*)\]\]", r"\1", s)
    s = re.sub(r"\[\[([^\]]*)\]\]", r"\1", s)
    s = re.sub(r"\[https?://\S+\s+([^\]]+)\]", r"\1", s)
    s = re.sub(r"<br\s*/?>", " ", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = s.replace("'''", "").replace("''", "")
    return re.sub(r"\s+", " ", s).strip(" :;")


def parse_wiki_sarbatori(wikitext):
    m = re.search(r"^==\s*Sărbători\s*==\s*$", wikitext, flags=re.M | re.I)
    if not m:
        return []
    rest = wikitext[m.end():]
    n = re.search(r"^==[^=].*$", rest, flags=re.M)
    section = rest[:n.start()] if n else rest
    group, items = "", []
    for line in section.splitlines():
        h = re.match(r"^===+\s*(.+?)\s*===+\s*$", line)
        if h:
            group = clean_wiki(h.group(1))
            continue
        b = re.match(r"^(\*+)\s*(.*)$", line)
        if not b:
            continue
        depth, txt = len(b.group(1)), clean_wiki(b.group(2))
        if not txt:
            continue
        if depth == 1 and b.group(2).rstrip().endswith(":"):
            group = txt
            continue
        items.append((group, txt))
    return items


def fetch_sarbatori_ro(d):
    title = f"{d.day} {LUNI[d.month - 1]}"
    url = "https://ro.wikipedia.org/w/api.php?" + urllib.parse.urlencode({
        "action": "query", "prop": "revisions", "rvprop": "content", "rvslots": "main",
        "titles": title, "format": "json", "formatversion": 2})
    data = get_json(url)
    wt = data["query"]["pages"][0]["revisions"][0]["slots"]["main"]["content"]
    items = parse_wiki_sarbatori(wt)
    if not items:
        raise ValueError("secțiunea Sărbători negăsită")
    return items


def fetch_public_holidays(cc, year):
    return get_json(f"https://date.nager.at/api/v3/PublicHolidays/{year}/{cc}")


def holidays_for(cfg_h, today):
    today_s, per_country, upcoming = today.isoformat(), {}, {}
    for cc in cfg_h["countries"]:
        try:
            lst = fetch_public_holidays(cc, today.year)
            if cc in cfg_h.get("upcoming_for", []):
                try:
                    lst = lst + fetch_public_holidays(cc, today.year + 1)
                except Exception:
                    pass
            hits = [h for h in lst if h["date"] == today_s]
            if hits:
                per_country[cc] = [h.get("localName") or h["name"] for h in hits]
            if cc in cfg_h.get("upcoming_for", []):
                nxt = [h for h in lst if h["date"] > today_s]
                if nxt:
                    n = min(nxt, key=lambda h: h["date"])
                    upcoming[cc] = (n.get("localName") or n["name"], date.fromisoformat(n["date"]))
        except Exception as e:
            warn(f"sărbători legale {cc}", e)
    return per_country, upcoming


def render_holidays(today, saints, saints_src, per_country, upcoming):
    p = ['<div class="grid two">']
    p.append('<div class="card"><h2>🕯️ Sfinți și sărbători religioase</h2>')
    if saints:
        groups = {}
        for g, t in saints:
            groups.setdefault(g, []).append(t)
        for g, lst in groups.items():
            if g:
                p.append(f"<h3>{esc(g)}</h3>")
            p.append('<ul class="plain">' + "".join(f"<li>{esc(t)}</li>" for t in lst[:8]) + "</ul>")
        p.append(f'<p class="muted tiny">Sursă: {esc(saints_src)}</p>')
    else:
        p.append(soft_error("sărbători religioase"))
    p.append("</div>")
    p.append('<div class="card"><h2>🎈 Ce se mai sărbătorește azi</h2>')
    if per_country:
        p.append('<ul class="plain">')
        for cc, names in per_country.items():
            p.append(f"<li>{flag(cc)} <b>{esc(TARI.get(cc, cc))}</b>: {esc(', '.join(names))}</li>")
        p.append("</ul>")
    else:
        p.append('<p class="muted">Azi nu e sărbătoare legală în țările urmărite – zi obișnuită, dar a ta 😌</p>')
    if upcoming:
        p.append("<h3>📅 Următoarea sărbătoare legală</h3><ul class=\"plain\">")
        for cc, (name, d) in upcoming.items():
            left = (d - today).days
            when = "mâine" if left == 1 else f"peste {left} zile"
            p.append(f"<li>{flag(cc)} {esc(name)} – {d.day} {LUNI[d.month - 1]} ({when})</li>")
        p.append("</ul>")
    p.append("</div></div>")
    return "".join(p)


# ───────────────────────── ȘTIRI ─────────────────────────

def feed_url(f):
    if "url" in f:
        return f["url"]
    loc = "hl=ro&gl=RO&ceid=RO:ro"
    if f.get("gnews_top"):
        return f"https://news.google.com/rss?{loc}"
    if "gnews_topic" in f:
        return f"https://news.google.com/rss/headlines/section/topic/{f['gnews_topic']}?{loc}"
    if "gnews" in f:
        return "https://news.google.com/rss/search?q=" + urllib.parse.quote(f["gnews"]) + "&" + loc
    raise ValueError("feed necunoscut")


def parse_feed(raw, label=""):
    root = ET.fromstring(raw)
    items = []
    for it in root.iter():
        if it.tag.split("}")[-1] not in ("item", "entry"):
            continue
        title = link = source = None
        for ch in it:
            t = ch.tag.split("}")[-1]
            if t == "title":
                title = (ch.text or "").strip()
            elif t == "link":
                link = (ch.text or "").strip() or ch.get("href")
            elif t == "source":
                source = (ch.text or "").strip()
        if not title or not link:
            continue
        if source and title.endswith(" - " + source):
            title = title[: -len(source) - 3]
        elif not source and " - " in title:
            title, source = title.rsplit(" - ", 1)
        items.append({"title": title.strip(), "link": link, "source": source or label})
    return items


def fetch_news_category(feeds, n):
    lists = []
    for f in feeds:
        try:
            lists.append(parse_feed(http_get(feed_url(f), 20), f.get("label", "")))
        except Exception as e:
            warn("știri", e)
    out, seen, i = [], set(), 0
    while len(out) < n and any(i < len(l) for l in lists):  # amestec echilibrat între surse
        for l in lists:
            if i < len(l):
                key = re.sub(r"\W+", "", l[i]["title"].lower())[:45]
                if key not in seen:
                    seen.add(key)
                    out.append(l[i])
                    if len(out) >= n:
                        break
        i += 1
    return out


def render_news(title, emoji, cats):
    p = [f'<h2 class="sec">{emoji} {esc(title)}</h2><div class="grid three">']
    for name, items in cats.items():
        p.append(f'<div class="card"><h3 class="first">{esc(name)}</h3>')
        if not items:
            p.append(soft_error(name))
        else:
            p.append('<ul class="news">')
            for it in items:
                src = f' <span class="src">{esc(it["source"])}</span>' if it["source"] else ""
                p.append(f'<li><a href="{esc(it["link"])}" target="_blank" rel="noopener">{esc(it["title"])}</a>{src}</li>')
            p.append("</ul>")
        p.append("</div>")
    p.append("</div>")
    return "".join(p)


# ───────────────────────── CURS VALUTAR ─────────────────────────

def parse_bnr(raw):
    root = ET.fromstring(raw)
    out = {}
    for el in root.iter():
        if el.tag.split("}")[-1] == "Cube" and el.get("date"):
            day = {}
            for r in el:
                if r.tag.split("}")[-1] == "Rate" and r.text:
                    day[r.get("currency")] = float(r.text) / float(r.get("multiplier") or 1)
            if day:
                out[el.get("date")] = day
    return out


def fetch_fx(today, days):
    data = {}
    try:
        for y in (today.year - 1, today.year) if today.month <= 2 else (today.year,):
            data.update(parse_bnr(http_get(f"https://www.bnr.ro/files/xml/years/nbrfxrates{y}.xml", 25)))
        if data:
            return data, "BNR"
    except Exception as e:
        warn("curs BNR", e)
    try:  # plan B: BCE prin Frankfurter
        start = (today - timedelta(days=days + 10)).isoformat()
        j = get_json(f"https://api.frankfurter.dev/v1/{start}..?base=EUR&symbols=RON,USD,CZK")
        for dt, r in j["rates"].items():
            data[dt] = {"EUR": r["RON"], "USD": r["RON"] / r["USD"], "CZK": r["RON"] / r["CZK"]}
        if data:
            STATUS[:] = [x for x in STATUS if not x.startswith("curs BNR")]
            return data, "BCE (Frankfurter)"
    except Exception as e:
        warn("curs BCE", e)
    return {}, ""


def spark(vals, w=130, h=36):
    lo, hi = min(vals), max(vals)
    span = (hi - lo) or 1
    pts = " ".join(f"{i * (w - 4) / (len(vals) - 1) + 2:.1f},{h - 4 - (v - lo) / span * (h - 8):.1f}"
                   for i, v in enumerate(vals))
    return (f'<svg class="spark" viewBox="0 0 {w} {h}" width="{w}" height="{h}" aria-hidden="true">'
            f'<polyline points="{pts}" fill="none" stroke="currentColor" stroke-width="2" '
            f'stroke-linecap="round" stroke-linejoin="round"/></svg>')


def render_fx(data, src, cfg, today):
    if not data:
        return '<div class="card"><h2>💶 Curs valutar</h2>' + soft_error("curs valutar") + "</div>"
    dates = sorted(data)[-(cfg["days"] + 1):]
    rows = []
    for cur in cfg["show"]:
        s = [data[d][cur] for d in dates if cur in data[d]]
        if len(s) >= 2:
            rows.append((f"1 {cur}", "RON", s, 4 if cur == "CZK" else 4))
    for a, b in cfg.get("cross", []):
        s = [data[d][a] / data[d][b] for d in dates if a in data[d] and b in data[d]]
        if len(s) >= 2:
            rows.append((f"1 {a}", b, s, 3))
    p = ['<h2 class="sec">💶 Curs valutar</h2><div class="grid three">']
    for label, unit, s, dec in rows:
        last, prev = s[-1], s[-2]
        diff = last - prev
        arrow, cls = ("▲", "up") if diff > 0 else ("▼", "down") if diff < 0 else ("•", "flat")
        p.append(f'<div class="card fx"><div class="fxl">{esc(label)} =</div>'
                 f'<div class="fxv">{last:.{dec}f} <small>{esc(unit)}</small></div>'
                 f'<div class="fxd {cls}">{arrow} {abs(diff):.{dec}f} față de ziua anterioară</div>'
                 f'{spark(s)}<div class="muted tiny">{len(s)} zile · min {min(s):.{dec}f} · max {max(s):.{dec}f}</div></div>')
    p.append(f'</div><p class="muted tiny">Sursă: {esc(src)} · ultima zi cu curs: {dates[-1]}</p>')
    return "".join(p)


# ───────────────────────── DEMO ─────────────────────────

def demo_weather(locs, today):
    import random
    rnd = random.Random(7)
    out = []
    for i, loc in enumerate(locs):
        base = 3 + (i * 2) % 12
        days = []
        for k in range(5):
            tm = base + 3 + k - rnd.random()
            dd = today + timedelta(days=k)
            days.append({"date": dd.isoformat(), "code": [3, 61, 2, 0, 71][(k + i) % 5], "tmax": tm, "tmin": tm - 7,
                         "fmax": tm - 2, "fmin": tm - 9, "pop": [40, 70, 20, 5, 55][(k + i) % 5], "precip": 1.2,
                         "wind": [18, 34, 12, 8, 20][(k + i) % 5], "uv": 1, "sunrise": f"{dd.isoformat()}T07:04",
                         "sunset": f"{dd.isoformat()}T15:56"})
        out.append({"loc": loc, "cur": {"temp": base + 1, "feels": base - 2, "code": 3, "wind": 14, "hum": 78}, "days": days})
    return out


def demo_fx(today, n=40):
    import random
    rnd = random.Random(3)
    data, e, u, c = {}, 5.09, 4.38, 0.2092
    for k in range(n, -1, -1):
        d = today - timedelta(days=k)
        if d.weekday() < 5:
            e += rnd.uniform(-0.012, 0.012); u += rnd.uniform(-0.02, 0.02); c += rnd.uniform(-0.0006, 0.0006)
            data[d.isoformat()] = {"EUR": e, "USD": u, "CZK": c}
    return data


DEMO_NEWS = {
    "📰 Generale": [("Exemplu de titlu: se anunță vreme mai blândă la final de săptămână", "Sursă demo")] * 3,
    "🏛️ Politică": [("Exemplu de titlu: ședință importantă în Parlament azi", "Sursă demo")] * 3,
    "⚽ Sport": [("Exemplu de titlu: programul etapei din weekend", "Sursă demo")] * 3,
}


def demo_news(cats):
    out = {}
    for name in cats:
        out[name] = [{"title": f"Exemplu de titlu #{i + 1} la „{name.split(' ', 1)[-1]}” (date demo)",
                      "link": "#", "source": "Sursă demo"} for i in range(4)]
    return out


# ───────────────────────── PAGINA ─────────────────────────

def build(args):
    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    tz = ZoneInfo(cfg.get("timezone", "Europe/Prague"))
    now = datetime.now(tz)
    if args.edition:
        edition = args.edition
    else:
        edition = "morning" if now.hour < 12 else "evening"
    today = now.date()
    n_news = cfg.get("news_items_per_category", 6)
    demo = args.demo
    sections, summary = [], []

    name = cfg.get("name", "").strip()
    greet = ("Bună dimineața" if edition == "morning" else "Bună seara") + (f", {name}" if name else "")
    greet += " ☕" if edition == "morning" else " 🌙"
    date_txt = f"{ZILE[today.weekday()].capitalize()}, {today.day} {LUNI[today.month - 1]} {today.year}"
    qtext, qauthor = alege_citat(edition, today)
    quote_html = (f'<blockquote class="quote">„{esc(qtext)}”'
                  + (f'<cite>— {esc(qauthor)}</cite>' if qauthor else '') + '</blockquote>')

    for sec in cfg["sections"]:
        try:
            if sec == "weather":
                if demo:
                    wl = demo_weather(cfg["locations"], today)
                else:
                    wl = []
                    for loc in cfg["locations"]:
                        try:
                            wl.append(fetch_weather(loc))
                        except Exception as e:
                            warn(f"vreme {loc['name']}", e)
                if wl:
                    sections.append(render_weather(wl, edition, cfg.get("show_clothing", True), today, cfg.get("panels")))
                    w0 = next((w for w in wl if w["loc"]["name"] == (cfg.get("panels") or [wl[0]["loc"]["name"]])[0]), wl[0])
                    summary.append(f"{w0['loc']['name']} {w0['cur']['temp']:.0f}° {WMO.get(w0['cur']['code'], ('',''))[0]}"
                                   f" (azi {w0['days'][0]['tmin']:.0f}°/{w0['days'][0]['tmax']:.0f}°)")
                else:
                    sections.append('<div class="card"><h2>🌦️ Vremea</h2>' + soft_error("vremea") + "</div>")

            elif sec == "calendar":
                urls = [u.strip() for u in os.environ.get("ICAL_URLS", "").splitlines() if u.strip()]
                pw = "demo" if demo else os.environ.get("PAGE_PASSWORD", "")
                if demo:
                    ev = {today: [{"time": "09:30", "title": "Exemplu: ședință scurtă", "where": "Online", "cal": ""},
                                  {"time": None, "title": "Exemplu: zi de naștere – Maria 🎂", "where": "", "cal": ""}],
                          today + timedelta(days=1): [{"time": "17:00", "title": "Exemplu: sală", "where": "", "cal": ""}]}
                elif urls and pw:
                    ev = fetch_calendar_events(urls, tz, [today, today + timedelta(days=1)])
                else:
                    ev = None
                if ev is not None:
                    sections.append(render_calendar(ev, today, pw, demo))
                    summary.append(f"{len(ev.get(today, []))} în calendar azi")
                else:
                    why = ("Lipsește parola paginii (PAGE_PASSWORD)." if urls else
                           "Calendarul nu e conectat încă (secretul ICAL_URLS).")
                    sections.append(f'<div class="card"><h2>🗓️ Calendarul tău</h2><p class="muted">{why}</p></div>')

            elif sec == "holidays":
                if demo:
                    saints = [("Ortodoxă", "Sf. Mc. Clement, episcopul Romei (exemplu demo)"),
                              ("Romano-catolică", "Sf. Andrei Dung-Lac și tovarășii (exemplu demo)")]
                    src = "date demo"
                    per_c = {"RO": ["Exemplu demo"], "CZ": ["Exemplu demo"]}
                    upc = {"RO": ("Sfântul Andrei", date(2026, 11, 30)), "CZ": ("Ziua Independenței", date(2026, 12, 25))}
                else:
                    try:
                        saints, src = fetch_sarbatori_ro(today), "Wikipedia (ro)"
                    except Exception as e:
                        warn("sfinții zilei", e)
                        fb = SARBATORI_FIXE.get(today.strftime("%m-%d"))
                        saints, src = ([("", fb)], "listă internă – sărbători mari") if fb else ([], "")
                    per_c, upc = holidays_for(cfg["holidays"], today)
                sections.append(render_holidays(today, saints, src, per_c, upc))

            elif sec in ("news_ro", "news_world", "news_tech"):
                key = {"news_ro": "ro", "news_world": "world", "news_tech": "tech"}[sec]
                feeds = cfg["news"][key]
                cats = demo_news(feeds) if demo else {n: fetch_news_category(f, n_news) for n, f in feeds.items()}
                ttl = {"ro": ("Știri din România", "🇷🇴"), "world": ("Știri din lume", "🌍"),
                       "tech": ("Știință, tehnologie și auto", "🔬")}[key]
                sections.append(render_news(ttl[0], ttl[1], cats))

            elif sec == "fx":
                if demo:
                    data, src = demo_fx(today), "date demo"
                else:
                    data, src = fetch_fx(today, cfg["fx"]["days"])
                sections.append(render_fx(data, src, cfg["fx"], today))
                if data:
                    last = data[sorted(data)[-1]]
                    summary.append(f"EUR {last['EUR']:.2f} lei")
        except Exception as e:
            warn(f"secțiunea {sec}", e)
            sections.append(f'<div class="card">{soft_error(sec)}</div>')

    tpl = (ROOT / "template.html").read_text(encoding="utf-8")
    footer = f"Generat {now.strftime('%d.%m.%Y la %H:%M')} ({cfg.get('timezone')}) · surse: Open-Meteo, BNR, Nager.Date, Wikipedia, Google News, BBC"
    if STATUS:
        footer += "<br>⚠️ " + esc(" · ".join(STATUS[:6]))
    page = (tpl.replace("{{TITLE}}", esc(cfg.get("title", "Raport")))
            .replace("{{GREETING}}", esc(greet)).replace("{{DATE}}", esc(date_txt))
            .replace("{{QUOTE}}", quote_html).replace("{{EDITION}}", edition)
            .replace("{{SECTIONS}}", "\n".join(sections)).replace("{{FOOTER}}", footer))
    out = ROOT / args.out
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.html").write_text(page, encoding="utf-8")
    for f in ("manifest.webmanifest", "icon.svg", "icon-192.png", "icon-512.png"):
        if (ROOT / "assets" / f).exists():
            (out / f).write_bytes((ROOT / "assets" / f).read_bytes())
    (out / ".nojekyll").write_text("")
    (out / "summary.txt").write_text(" · ".join(summary) or "Raportul tău e gata", encoding="utf-8")
    print(f"OK -> {out / 'index.html'}  (ediția: {edition}, avertismente: {len(STATUS)})")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--edition", choices=["morning", "evening"])
    ap.add_argument("--out", default="site")
    build(ap.parse_args())
