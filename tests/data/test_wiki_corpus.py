import pytest

from vtts.data.wiki_corpus import RATE, accept, eu_portuguese, seconds, split_sentences, unit_count


def test_split_latin_keeps_marks():
    assert split_sentences("Hola amigo. ¿Cómo estás? ¡Vamos!", "es") == ["Hola amigo.", "¿Cómo estás?", "¡Vamos!"]
    assert split_sentences("  ", "es") == []


def test_reject_double_space():
    assert not accept("Ocupa una superficie de  kilómetros cuadrados en total.", "es")
    assert not accept("यह भौगोलिक अन्वेषण,  यूरोपीय इतिहास का हिस्सा था.", "hi")


def test_thai_skips_chunks_next_to_numbers_or_foreign_words():
    text = "เป็นนักแสดงชาวอเมริกันเชื้อสายออสเตรเลียที่มีชื่อเสียง (Actor) ราชสำนักหมิงมีคำสั่งให้ปลูกต้นไม้จำนวน 100 ต้น"
    assert split_sentences(text, "th") == []
    text = "ประเทศไทยเป็นประเทศที่ตั้งอยู่ในเอเชียตะวันออกเฉียงใต้  มีประชากรประมาณหกสิบหกล้านคน"
    assert split_sentences(text, "th") == []  # double space: removed content between them


def test_accept_spanish():
    assert accept("Madrid es la capital de España y su ciudad más poblada.", "es")
    assert accept("¿Sabes dónde está la estación de tren más cercana?", "es")
    assert accept("El niño, que tenía mucho miedo, corrió hacia su casa.", "es")


def test_reject_spanish():
    assert not accept("La ciudad fue fundada en 1541 por Pedro de Valdivia.", "es")
    assert not accept("La ONU fue fundada después de la Segunda Guerra Mundial.", "es")
    assert not accept("El río (que nace en los Andes) cruza todo el país.", "es")
    assert not accept("Fue rey durante el siglo XIV en toda la región.", "es")
    assert not accept("Madrid es la capital de España y su ciudad más poblada", "es")
    assert not accept("Hola amigo.", "es")
    assert not accept("la ciudad es la capital de España y su ciudad más poblada.", "es")
    assert not accept("Se conocen muchas especies de aves, reptiles, peces, etc.", "es")
    assert not accept("La obra fue escrita por el autor inglés J.", "es")
    assert not accept("¿Sabes dónde está la estación de tren más cercana.", "es")
    assert not accept("Madrid es la capital de España y su ciudad más poblada...", "es")
    assert not accept("Madrid es la capital de España y su ciudad más poblada .", "es")
    assert not accept("La ciudad de São Paulo es la más grande de Brasil.", "es")


def test_accept_indonesian_reduplication_and_reject():
    assert accept("Anak-anak itu bermain di halaman sekolah setiap sore.", "id")
    assert not accept("Kota ini memiliki banyak taman, museum, dll.", "id")
    assert not accept("Ia lahir pada tahun 1945 di kota Surabaya, Jawa Timur.", "id")
    assert not accept("Pada hari Jum'at mereka pergi ke masjid bersama keluarga.", "id")
    assert not accept("Kota ini adalah tempat yang sangat indah dan ramai.-", "id")


def test_accept_german():
    assert accept("Die Stadt liegt am Ufer des Rheins und hat einen großen Hafen.", "de")
    assert accept("Weißt du, wo der nächste Bahnhof ist?", "de")
    assert not accept("Die Stadt hat z. B. einen großen Hafen am Fluss.", "de")
    assert not accept("Die Stadt wurde im Jahr 1241 erstmals urkundlich erwähnt.", "de")
    assert not accept("Er war Mitglied der SPD und des Bundestages bis zum Tod.", "de")
    assert split_sentences("Er kam. Sie ging.", "de") == ["Er kam.", "Sie ging."]


def test_accept_portuguese():
    assert accept("O Brasil é o maior país da América do Sul em área.", "pt")
    assert accept("Você pode me dizer onde fica a estação de trem?", "pt")
    assert not accept("¿Você pode me dizer onde fica a estação de trem?", "pt")
    assert not accept("A cidade de Madrid é famosa pelo museu del Prado, señor.", "pt")


def test_accept_italian_elision_and_reject():
    assert accept("L'Italia è una repubblica parlamentare dell'Europa meridionale.", "it")
    assert accept("Perché la città è così famosa nel mondo intero?", "it")
    assert not accept("Il XX secolo fu un periodo di grandi cambiamenti.", "it")
    assert not accept("La chiesa fu costruita nel 1350 dai monaci.", "it")
    assert not accept("Il libro fu scritto da un autore dell'ONU molto noto.", "it")
    assert not accept("La regione è famosa per vini, formaggi, salumi, ecc.", "it")
    assert not accept("Il paese si trova in una valle molto bella, un po'.", "it")


def test_accept_turkish_suffix_apostrophe_and_reject():
    assert accept("Türkiye'nin en kalabalık şehri İstanbul'dur ve çok güzeldir.", "tr")
    assert accept("Ilık bir rüzgâr şehrin üzerinden hafifçe esiyordu.", "tr")
    assert not accept("Ankara ABD ile ilişkilerini geliştirdi ve anlaşma yaptı.", "tr")
    assert not accept("Şehir 1923 yılında başkent ilan edildi ve büyüdü.", "tr")
    assert not accept("Bu konuda birçok kitap, dergi, makale vb. yazıldı.", "tr")


@pytest.mark.parametrize("s", [
    "Os preços estão a aumentar em todo o país desde o ano passado.",
    "Ele continua a trabalhar na mesma empresa de sempre.",
    "A aldeia pertence ao concelho de Viseu, no centro do país.",
    "Ela apanhou o comboio para Lisboa logo de manhã.",
    "O treinador anunciou a equipa para o jogo de domingo.",
    "De facto, ninguém sabia onde ele estava naquela noite.",
    "A acção decorre numa pequena cidade do interior.",
    "O director do museu falou com os jornalistas.",
    "O crescimento económico foi muito forte nesse período.",
    "Ela ganhou um prémio pelo seu trabalho com crianças.",
    "O jogador marcou um golo no último minuto da partida.",
    "Guarde o ficheiro antes de fechar o programa, por favor.",
    "Vamos jogar ténis no clube depois do almoço.",
    "António nasceu numa pequena vila perto do mar.",
    "A espécie ocorre em várias ilhas, nomeadamente na Madeira e nos Açores.",
    "O clube registou o melhor resultado da sua história nesse ano.",
])
def test_european_portuguese_rejected(s):
    assert eu_portuguese(s) and not accept(s, "pt")


@pytest.mark.parametrize("s", [
    "Os preços estão aumentando em todo o país desde o ano passado.",
    "O ônibus chegou atrasado e eu perdi a reunião.",
    "O crescimento econômico foi muito forte nesse período.",
    "De fato, ninguém sabia onde ele estava naquela noite.",
    "O diretor do museu falou com os jornalistas.",
    "A cidade fica a cargo do governo estadual desde então.",
    "Ele ficou a favor da proposta apresentada pelo prefeito.",
    "Ela é muito amiga do time inteiro da escola.",
    "O sumo sacerdote entrou no templo com os outros.",
])
def test_brazilian_portuguese_kept(s):
    assert not eu_portuguese(s) and accept(s, "pt")


def test_hindi_danda_and_accept():
    parts = split_sentences("भारत एक विशाल देश है। यहाँ अनेक भाषाएँ बोली जाती हैं।", "hi")
    assert parts == ["भारत एक विशाल देश है.", "यहाँ अनेक भाषाएँ बोली जाती हैं."]
    assert accept("यहाँ अनेक भाषाएँ बोली जाती हैं.", "hi")
    assert accept("क्या आप मेरे साथ बाज़ार चलेंगे?", "hi")
    assert not accept("यहाँ अनेक भाषाएँ बोली जाती हैं", "hi")
    assert not accept("सन १९४७ में भारत को आज़ादी मिली थी.", "hi")
    assert not accept("सन 1947 में भारत को आज़ादी मिली थी.", "hi")
    assert not accept("भारत में NASA जैसी कई संस्थाएँ काम करती हैं.", "hi")
    assert not accept("भारत (इंडिया) दक्षिण एशिया का देश है.", "hi")
    assert not accept("भारत एक देश है.", "hi")


def test_arabic_split_and_accept():
    parts = split_sentences("ذهب الولد إلى المدرسة صباحا. هل تعرف أين يقع المسجد الكبير؟ نعم!", "ar")
    assert parts == ["ذهب الولد إلى المدرسة صباحا.", "هل تعرف أين يقع المسجد الكبير؟", "نعم!"]
    assert accept("ذهب الولد إلى المدرسة في الصباح الباكر.", "ar")
    assert accept("هل تعرف أين يقع المسجد الكبير في المدينة؟", "ar")
    assert accept("كتب الشاعر قصيدة طويلة عن البحر، ثم نشرها.", "ar")
    assert not accept("ذهب الولد إلى المدرسة في الصباح الباكر", "ar")
    assert not accept("ولد في عام 1947 في القاهرة المصرية.", "ar")
    assert not accept("ولد في عام ١٩٤٧ في القاهرة المصرية.", "ar")
    assert not accept("قال إن NASA أطلقت الصاروخ أمس.", "ar")
    assert not accept("قال إن الوكالة (ناسا) أطلقت الصاروخ.", "ar")
    assert not accept("هذا كتاب جميل.", "ar")
    assert seconds("ذَهَبَ الولد إلى المدرسة.", "ar") == 18 / 9.5  # letters, not vowel marks


def test_thai_joins_chunks_into_utterances():
    a = "ประเทศไทยเป็นประเทศที่ตั้งอยู่ในเอเชียตะวันออกเฉียงใต้"   # 52
    b = "มีประชากรประมาณหกสิบหกล้านคน"                              # 28
    text = f"{a} {b} ต่าง ๆ"
    assert split_sentences(text, "th") == [f"{a} {b} ต่างๆ"]
    assert accept(f"{a} {b} ต่างๆ", "th")


def test_thai_packing_respects_limits_and_breaks():
    a = "ก" * 40
    out = split_sentences(" ".join([a] * 7), "th")       # 286 chars -> 3 balanced utterances
    assert [len(u) for u in out] == [81, 122, 81] or [len(u) for u in out] == [122, 81, 81] \
        or [len(u) for u in out] == [81, 81, 122]
    assert " ".join(out) == " ".join([a] * 7)
    a = "ก" * 50
    # never across a non-plain chunk; the chunks touching it are dropped (cut-off clauses)
    out = split_sentences(f"{a} {a}x {a} 100 {a} {a}", "th")
    assert out == [a]
    long_chunk = "ข" * 160
    assert split_sentences(f"{a} {long_chunk} {a}", "th") == [a, a]
    assert not accept(long_chunk, "th")


def test_thai_accept():
    assert accept("มีประชากรประมาณหกสิบหกล้านคน ซึ่งส่วนใหญ่นับถือศาสนาพุทธ", "th")
    assert not accept("มีประชากรประมาณ ๖๖ ล้านคน", "th")
    assert not accept("มีประชากรประมาณ๖๖ล้านคนในประเทศไทยทั้งหมด", "th")
    assert not accept("ประเทศไทยเป็นประเทศในเอเชียThailand", "th")
    assert not accept("กรุงเทพฯเป็นเมืองหลวงของประเทศไทยมาช้านาน", "th")
    assert not accept("ประเทศไทย" * 20, "th")
    assert not accept("ประเทศไทย", "th")



def test_accept_russian():
    assert accept("Москва является столицей Российской Федерации и крупнейшим городом страны.", "ru")
    assert accept("Ты знаешь, где находится ближайшая станция метро?", "ru")
    assert accept("Он родился в семье учителя и с детства любил читать книги.", "ru")
    assert not accept("В 1990 году он переехал в Москву и начал работать.", "ru")
    assert not accept("Он работал в СССР и в других странах Восточной Европы.", "ru")
    assert not accept("Это был, т. е. оказался, хороший человек и верный друг.", "ru")
    assert not accept("Город стоит на берегу реки (притока Волги) в центре области.", "ru")
    assert not accept("Он работал в Berlin и в других городах Европы.", "ru")
    assert not accept("Москва является столицей Российской Федерации", "ru")


def test_accept_polish():
    assert accept("Warszawa jest stolicą Polski i największym miastem w kraju.", "pl")
    assert accept("Czy wiesz, gdzie jest najbliższa stacja metra?", "pl")
    assert not accept("W 1990 roku przeprowadził się do Krakowa i zaczął pracę.", "pl")
    assert not accept("Pracował w PKP i w innych firmach przez wiele lat.", "pl")
    assert not accept("Był to dobry człowiek, tzw. przyjaciel całej rodziny.", "pl")
    assert not accept("Miasto leży nad rzeką Москва w środkowej części kraju.", "pl")


@pytest.mark.parametrize("text,lang,n", [
    ("Hola amigo.", "es", 5),                     # ho-la a-mi-go
    ("Bom dia, João.", "pt", 3),                   # vowel groups: o, ia, oão (hiatus undercounted)
    ("Selamat pagi.", "id", 5),
    ("Bonjour, l'école.", "fr", 5),                # o, ou, é, o, e (final e counted)
    ("Guten Morgen, Bäcker.", "de", 6),            # gu-ten mor-gen bä-cker
    ("Ciao, l'acqua è buona.", "it", 6),            # vowel groups: iao, a, ua, è, uo, a
    ("Dağ yolu, İstanbul'a.", "tr", 7),            # a, o, u, İ, a, u, a
    ("भारत देश", "hi", 5),                         # भा र त दे श
    ("क्या", "hi", 1),                              # क् + या
    ("สวัสดีครับ", "th", 7),                         # spacing chars ส ว ส ด ค ร บ
    ("Россия, привет.", "ru", 5),                   # every vowel letter: Ро-сси-я при-вет
    ("Ciasto i dziecko.", "pl", 5),                 # cia-sto i dzie-cko: softening i not counted
])
def test_unit_count(text, lang, n):
    assert unit_count(text, lang) == n


def test_seconds_uses_rate():
    assert seconds("Hola amigo.", "es") == 5 / RATE["es"]


def test_dutch_swedish_norwegian_sentences():
    assert accept("Het is een mooie dag in België, zei hij.", "nl")
    assert not accept("Het is een mooie dag in België, zei J. Jansen.", "nl")  # initial
    assert not accept("Hij woonde o.a. in Utrecht en in Leiden.", "nl")
    assert not accept("Het kost bijv. tien euro.", "nl") and not accept("Het jaar 1999 was koud.", "nl")


def test_french_accept():
    assert accept("L'Europe est un continent très peuplé et riche en histoire.", "fr")
    assert accept("La ville de Saint-Étienne est située dans la Loire.", "fr")
    assert split_sentences("Qui est-ce que tu as vu hier soir au marché ?", "fr") == [
        "Qui est-ce que tu as vu hier soir au marché?"]
    assert split_sentences("Aujourd’hui, les enfants vont à l’école en bus.", "fr") == [
        "Aujourd'hui, les enfants vont à l'école en bus."]
    assert not accept("Le roi Louis XIV régna sur la France pendant longtemps.", "fr")
    assert not accept("La ville compte 2 000 habitants et une grande église.", "fr")
    assert not accept("Il est né au XIXe siècle dans une petite ville.", "fr")
    assert not accept("Les fruits, les légumes, les fleurs, etc.", "fr")


def test_accept_finnish():
    assert accept("Helsinki on Suomen pääkaupunki ja suurin kaupunki.", "fi")
    assert accept("Tiedätkö, missä lähin rautatieasema on tässä kaupungissa?", "fi")
    assert not accept("Kaupungissa on paljon puistoja, kirjastoja jne.", "fi")
    assert not accept("Hän syntyi vuonna 1950 Helsingissä ja kuoli myöhemmin.", "fi")
    assert not accept("Yhtiön pääkonttori on Helsingissä, ja sen omistaa YLE.", "fi")
    assert seconds("Helsinki on Suomen pääkaupunki.", "fi") == unit_count("Helsinki on Suomen pääkaupunki.", "fi") / RATE["fi"]


def test_accept_greek():
    parts = split_sentences("Η Αθήνα είναι η πρωτεύουσα της Ελλάδας. Πού είναι το σπίτι σου; Έλα εδώ!", "el")
    assert parts == ["Η Αθήνα είναι η πρωτεύουσα της Ελλάδας.", "Πού είναι το σπίτι σου;", "Έλα εδώ!"]
    assert accept("Η Αθήνα είναι η πρωτεύουσα και μεγαλύτερη πόλη της Ελλάδας.", "el")
    assert accept("Πού βρίσκεται ο σταθμός του τρένου της πόλης;", "el")
    assert split_sentences("Πού είναι ο σταθμός; Εδώ.", "el") == ["Πού είναι ο σταθμός;", "Εδώ."]
    assert not accept("Υπάρχουν πολλά είδη, όπως πουλιά, ψάρια κλπ.", "el")
    assert not accept("Η πόλη ιδρύθηκε το 1834 από τον βασιλιά Όθωνα.", "el")
    assert not accept("Η πόλη είναι γνωστή για τα μνημεία της· ιδίως την Ακρόπολη.", "el")
    assert not accept("Η πόλη είναι η πρωτεύουσα της Ελλάδας", "el")
def test_accept_malay():
    assert accept("Kuala Lumpur ialah ibu negara Malaysia yang paling besar.", "ms")
    assert not accept("Kota ini mempunyai banyak taman, muzium, dll.", "ms")
    assert not accept("Beliau dilahirkan pada tahun 1957 di Kuala Lumpur.", "ms")
    assert not accept("Syarikat itu berpusat di Jln. Ampang, Kuala Lumpur.", "ms")
    assert RATE["ms"] == 5.5


def test_accept_tagalog_contractions():
    assert accept("Ang bahay ay may dalawampu't limang silid sa loob.", "tl")
    assert accept("Ang bahay ay may dalawampu’t limang silid sa loob.".replace("’", "'"), "tl")
    assert split_sentences("Ito’y isang bayan sa lalawigan ng Batangas.", "tl") == [
        "Ito'y isang bayan sa lalawigan ng Batangas."]
    assert not accept("Ang bahay ay may 'di limang silid sa loob.", "tl")
    assert not accept("Ang bahay ay may dalawampu't limang silid sa loob.", "ms")
    assert not accept("Ipinanganak siya noong 1990 sa Maynila, Pilipinas.", "tl")


def test_accept_swahili_ng_apostrophe():
    assert accept("Ng'ombe wa Juma ni mkubwa sana kuliko wote.", "sw")
    assert split_sentences("Ng’ombe wa Juma ni mkubwa sana kuliko wote.", "sw") == [
        "Ng'ombe wa Juma ni mkubwa sana kuliko wote."]
    assert not accept("Kumi na mbili n'go wa Juma ni mkubwa sana.", "sw")
    assert not accept("Alizaliwa mwaka 1990 katika mji wa Nairobi.", "sw")
