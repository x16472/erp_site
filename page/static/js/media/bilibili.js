import { createMediaPlayer } from './player.js';

export const BilibiliPlayer = {
    init(context) {
        return createMediaPlayer('bilibili', {
            name: 'BiliBili',
            storageKey: 'BilibiliVideo',
            endpoint: '/api/media/resolve',
        }, context);
    },
};
