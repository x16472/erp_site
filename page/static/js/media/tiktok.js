import { createMediaPlayer } from './player.js';

export const TiktokPlayer = {
    init(context) {
        return createMediaPlayer('tiktok', {
            name: 'TikTok',
            storageKey: 'TiktokVideo',
            endpoint: '/api/media/resolve',
        }, context);
    },
};
