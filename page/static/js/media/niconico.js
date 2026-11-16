import { createMediaPlayer } from './player.js';

export const NiconicoPlayer = {
    init(context) {
        return createMediaPlayer('niconico', {
            name: 'ニコニコ',
            storageKey: 'NiconicoVideo',
            endpoint: '/api/media/resolve',
        }, context);
    },
};
