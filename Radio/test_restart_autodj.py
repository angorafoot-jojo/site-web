"""Tests de la logique de dédoublonnage de file de restart_autodj.py.

Contexte (audit 06-25→07-01) : après le reset de minuit, le message du jour
jouait exactement 2× d'affilée (la 2e copie attendait dans la file de la
station). `queue_dup_delete_urls` doit repérer les doublons DOS À DOS
uniquement, sans toucher aux rediffusions légitimes espacées dans la journée.
"""
import unittest

from restart_autodj import queue_dup_delete_urls


def _item(n, song_id, is_played=False):
    return {
        "links": {"self": f"https://radio.example/api/station/1/queue/{n}"},
        "song": {"id": song_id, "text": song_id},
        "is_played": is_played,
    }


def _url(n):
    return f"https://radio.example/api/station/1/queue/{n}"


class QueueDupDeleteUrlsTest(unittest.TestCase):
    def test_file_vide(self):
        self.assertEqual(queue_dup_delete_urls("msg", []), [])

    def test_aucun_doublon(self):
        queue = [_item(1, "jingle"), _item(2, "bible1"), _item(3, "bible2")]
        self.assertEqual(queue_dup_delete_urls("msg", queue), [])

    def test_message_a_l_antenne_duplique_en_tete_de_file(self):
        # Le cas du bug : le message joue (play #1) ET attend en file (play #2).
        queue = [_item(10, "msg"), _item(11, "jingle"), _item(12, "bible1")]
        self.assertEqual(queue_dup_delete_urls("msg", queue), [_url(10)])

    def test_triple_lecture_comme_le_27_06(self):
        # réel/fichier = 3,00x le 27/06 : deux copies d'affilée en file.
        queue = [_item(10, "msg"), _item(11, "msg"), _item(12, "bible1")]
        self.assertEqual(queue_dup_delete_urls("msg", queue), [_url(10), _url(11)])

    def test_doublon_interne_a_la_file(self):
        queue = [_item(10, "jingle"), _item(11, "bible1"), _item(12, "bible1")]
        self.assertEqual(queue_dup_delete_urls("msg", queue), [_url(12)])

    def test_copie_non_consecutive_conservee(self):
        # Le message rejoué plus loin dans la file (autre bloc) est légitime.
        queue = [_item(10, "jingle"), _item(11, "msg"), _item(12, "bible1")]
        self.assertEqual(queue_dup_delete_urls("msg", queue), [])

    def test_antenne_non_fiable_ignore_le_titre_en_cours(self):
        # now_song_id=None (titre démarré avant le restart) : ne supprime pas
        # la tête de file même identique — ce serait la lecture LÉGITIME.
        queue = [_item(10, "msg"), _item(11, "jingle")]
        self.assertEqual(queue_dup_delete_urls(None, queue), [])

    def test_elements_deja_joues_ignores(self):
        queue = [_item(10, "msg", is_played=True), _item(11, "msg")]
        self.assertEqual(queue_dup_delete_urls("msg", queue), [_url(11)])

    def test_chanson_sans_id_jamais_comparee(self):
        queue = [{"links": {"self": _url(10)}, "song": {}, "is_played": False},
                 {"links": {"self": _url(11)}, "song": {}, "is_played": False}]
        self.assertEqual(queue_dup_delete_urls("msg", queue), [])

    def test_element_sans_lien_self_non_supprimable(self):
        queue = [{"song": {"id": "msg"}, "is_played": False}]
        self.assertEqual(queue_dup_delete_urls("msg", queue), [])


if __name__ == "__main__":
    unittest.main()
