import { createMediaPlayer } from './player.js';
import { YoutubeThumbnailApp } from './youtube_thumbnail.js';

export const YoutubePlayer = {
    init(context) {
        YoutubeThumbnailApp.UI.initEvents();
        return createMediaPlayer('youtube', {
            name: 'YouTube',
            storageKey: 'YoutubeVideo',
            endpoint: '/api/youtube/resolve',
        }, context);
    },
};
