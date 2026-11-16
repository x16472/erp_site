import { createMediaPlayer } from './player.js';

export const DouyinPlayer = {
    init(context) {
        return createMediaPlayer('douyin', {
            name: 'Douyin',
            storageKey: 'DouyinVideo',
            endpoint: '/api/media/resolve',
        }, context);
    },
};
