import { describe, it, expect, vi, afterEach } from 'vitest'
import { retrieveSharedFile } from './sharedFile'

function mockCaches(matchResult: Response | undefined) {
    const cacheDelete = vi.fn().mockResolvedValue(true)
    const cache = {
        match: vi.fn().mockResolvedValue(matchResult),
        delete: cacheDelete,
    }
    vi.stubGlobal('caches', { open: vi.fn().mockResolvedValue(cache) })
    return { cache, cacheDelete }
}

afterEach(() => {
    vi.unstubAllGlobals()
})

describe('retrieveSharedFile', () => {
    it('returns null when Cache API is unavailable', async () => {
        expect(await retrieveSharedFile()).toBeNull()
    })

    it('returns null when no shared file is stashed', async () => {
        const { cacheDelete } = mockCaches(undefined)
        expect(await retrieveSharedFile()).toBeNull()
        expect(cacheDelete).not.toHaveBeenCalled()
    })

    it('returns the stashed file with name and type, and deletes the entry', async () => {
        const stored = new Response('fake-image', {
            headers: {
                'Content-Type': 'image/png',
                'X-File-Name': encodeURIComponent('comprobante banco.png'),
            },
        })
        const { cacheDelete } = mockCaches(stored)

        const file = await retrieveSharedFile()
        expect(file).not.toBeNull()
        expect(file!.name).toBe('comprobante banco.png')
        expect(file!.type).toBe('image/png')
        expect(await file!.text()).toBe('fake-image')
        expect(cacheDelete).toHaveBeenCalledWith('/shared-comprobante')
    })

    it('falls back to default name when header is missing', async () => {
        const stored = new Response('x', { headers: { 'Content-Type': 'application/pdf' } })
        mockCaches(stored)

        const file = await retrieveSharedFile()
        expect(file!.name).toBe('comprobante')
    })
})
