from torrent_manager import PBSearcher, PBMonitor


class TestPBSearcher:
    def setup_method(self, method):
        self.searcher = PBSearcher("akira")

    def test_search_torrent_sorting(self, mock_response):
        results = self.searcher.search_torrent()
        torrent_names = [result.name for result in results]
        assert torrent_names == ["Torrent 3", "Torrent 1", "Torrent 2"]

    def test_search_torrent_no_results(self, mock_response_empty):
        results = self.searcher.search_torrent("non existing")
        assert results == []

    def test_search_torrent_http_error_handling(self, mock_response_404):
        assert self.searcher.search_torrent("its not working") == []

    def test_search_torrent_http_timeout(self, mock_timeout):
        results = self.searcher.search_torrent()
        assert results == []

    def test_look(self, mock_response):
        results = self.searcher.look()
        assert results

    def test_look_no_results(self, mock_response_empty):
        results = self.searcher.look()
        assert results is None

    def test_look_http_timeout(self, mock_timeout):
        results = self.searcher.look()
        assert results is None


class TestPBMonitor:
    def setup_method(self, method):
        self.monitor = PBMonitor(
            "attack on titan", episode_number=1, season_number=1)

    def test_look(self, mock_response):
        assert self.monitor.episode_number == 1
        self.monitor.look()
        assert self.monitor.episode_number == 2

    def test_look_max_seeders(self, mock_response):
        result = self.monitor.look()
        assert result.name == "Torrent 3"

    def test_look_no_episodes(self, mock_response_empty):
        assert self.monitor.episode_number == 1
        result = self.monitor.look()
        assert result is None
        assert self.monitor.episode_number == 1

    def test_look_max_seeders_with_size_limit(self, mock_response):
        self.monitor.size_limit_gb = 1
        result = self.monitor.look()
        assert result.name == "Torrent 1"

    def test_look_max_seeders_with_small_size_limit(self, mock_response):
        assert self.monitor.episode_number == 1
        self.monitor.size_limit_gb = 0.5
        result = self.monitor.look()
        assert result is None
        assert self.monitor.episode_number == 1

    def test_look_http_error(self, mock_response_404):
        self.monitor.look()
        assert self.monitor.episode_number == 1

    def test_look_timeout(self, mock_timeout):
        self.monitor.look()
        assert self.monitor.episode_number == 1

    def test_look_zero_episode(self, mock_response):
        self.monitor.episode_number = 0
        self.monitor.season_number = 0
        self.monitor.look()
        assert mock_response["query"] == "attack on titan s00e00"
        self.monitor.look()
        assert mock_response["query"] == "attack on titan s00e01"
