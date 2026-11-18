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


def test_accept_portuguese():
    assert accept("O Brasil é o maior país da América do Sul em área.", "pt")
    assert accept("Você pode me dizer onde fica a estação de trem?", "pt")
    assert not accept("¿Você pode me dizer onde fica a estação de trem?", "pt")
    assert not accept("A cidade de Madrid é famosa pelo museu del Prado, señor.", "pt")


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



@pytest.mark.parametrize("text,lang,n", [
    ("Hola amigo.", "es", 5),                     # ho-la a-mi-go
    ("Bom dia, João.", "pt", 3),                   # vowel groups: o, ia, oão (hiatus undercounted)
    ("Selamat pagi.", "id", 5),
    ("भारत देश", "hi", 5),                         # भा र त दे श
    ("क्या", "hi", 1),                              # क् + या
    ("สวัสดีครับ", "th", 7),                         # spacing chars ส ว ส ด ค ร บ
])
def test_unit_count(text, lang, n):
    assert unit_count(text, lang) == n


def test_seconds_uses_rate():
    assert seconds("Hola amigo.", "es") == 5 / RATE["es"]
