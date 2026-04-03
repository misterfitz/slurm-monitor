" slurm.vim — Vim/Neovim statusline integration for Slurm job status.
"
" Provides SlurmStatus() for your statusline showing running/pending
" jobs, fairshare score, and queue rank. Reads from a cache file
" populated by slurm-status.sh, so there's zero subprocess overhead.
"
" Install:
"   vim-plug:   Plug 'misterfitz/slurm-monitor'
"   lazy.nvim:  { 'misterfitz/slurm-monitor' }
"   packer:     use 'misterfitz/slurm-monitor'
"   manual:     source /path/to/plugin/slurm.vim
"
" Usage:
"   set statusline+=%{SlurmStatus()}
"
"   vim-airline:
"     let g:airline_section_y = '%{SlurmStatus()}'
"
"   lualine (Neovim):
"     lualine_y = { function() return vim.fn.SlurmStatus() end }

if exists('g:loaded_slurm_monitor')
    finish
endif
let g:loaded_slurm_monitor = 1

" Configuration
" g:slurm_monitor_cache_file  — path to cache file (default: /tmp/slurm-monitor-$USER.cache)
" g:slurm_monitor_refresh     — refresh interval in ms (default: 10000)
" g:slurm_monitor_user        — user to query (triggers slurm-status.sh if cache missing)
" g:slurm_monitor_qos         — QOS name to filter by (optional)
" g:slurm_monitor_fallback    — text to show when no data (default: '')
" g:slurm_monitor_alert       — show popup on job failures: 0=off, 1=on (default: 0)

let s:cache_file = get(g:, 'slurm_monitor_cache_file',
    \ '/tmp/slurm-monitor-' . $USER . '.cache')
let s:refresh_ms = get(g:, 'slurm_monitor_refresh', 10000)
let s:fallback = get(g:, 'slurm_monitor_fallback', '')
let s:alert = get(g:, 'slurm_monitor_alert', 0)
let s:cached_value = s:fallback
let s:last_fail_count = 0

function! SlurmStatus() abort
    return s:cached_value
endfunction

function! s:UpdateSlurmCache() abort
    if filereadable(s:cache_file)
        let l:lines = readfile(s:cache_file)
        if len(l:lines) > 0 && len(l:lines[0]) > 0
            " Strip tmux color codes (#[...]) if present
            let s:cached_value = substitute(l:lines[0], '#\[[^\]]*\]', '', 'g')
            return
        endif
    endif

    " If cache doesn't exist, try to generate it
    let l:plugin_dir = expand('<sfile>:p:h:h')
    let l:status_script = l:plugin_dir . '/scripts/slurm-status.sh'
    let l:user = get(g:, 'slurm_monitor_user', '')

    if executable(l:status_script)
        let l:cmd = l:status_script
        if len(l:user) > 0
            let l:cmd .= ' -u ' . l:user
        endif
        let l:qos = get(g:, 'slurm_monitor_qos', '')
        if len(l:qos) > 0
            let l:cmd .= ' -q ' . l:qos
        endif
        silent call system(l:cmd)
        " Re-read after generation
        if filereadable(s:cache_file)
            let l:lines = readfile(s:cache_file)
            if len(l:lines) > 0
                let s:cached_value = substitute(l:lines[0], '#\[[^\]]*\]', '', 'g')
                return
            endif
        endif
    endif

    let s:cached_value = s:fallback
endfunction

function! s:CheckSlurmFailures() abort
    if !s:alert
        return
    endif
    let l:json_file = s:cache_file . '.json'
    if !filereadable(l:json_file)
        return
    endif
    let l:content = join(readfile(l:json_file), '')
    if len(l:content) == 0
        return
    endif
    try
        let l:data = json_decode(l:content)
    catch
        return
    endtry
    let l:failed = get(l:data, 'failed_jobs', [])
    let l:count = len(l:failed)
    if l:count > s:last_fail_count && l:count > 0
        let l:new = l:count - s:last_fail_count
        if l:new == 1 && len(l:failed) > 0
            let l:name = get(l:failed[0], 'name', '?')
            let l:state = get(l:failed[0], 'state', 'FAILED')
            let l:msg = 'Slurm: job "' . l:name . '" ' . l:state
        else
            let l:msg = 'Slurm: ' . l:new . ' new job failure(s)'
        endif
        if has('nvim')
            lua vim.notify(vim.api.nvim_eval('l:msg'), vim.log.levels.ERROR)
        elseif has('popupwin')
            call popup_notification(l:msg, #{
                \ time: 5000,
                \ highlight: 'ErrorMsg',
                \ border: [],
                \ padding: [0, 1, 0, 1],
                \ pos: 'topright',
                \ col: &columns,
                \ line: 1,
                \ })
        else
            echohl ErrorMsg | echom l:msg | echohl None
        endif
    endif
    let s:last_fail_count = l:count
endfunction

" Initial load
call s:UpdateSlurmCache()

" Auto-refresh timer (Vim 8+ / Neovim)
if has('timers')
    function! s:TimerRefresh(timer) abort
        call s:UpdateSlurmCache()
        call s:CheckSlurmFailures()
        redrawstatus
    endfunction

    call timer_start(s:refresh_ms, function('s:TimerRefresh'), {'repeat': -1})
endif

" Also refresh on FocusGained (when switching back to vim)
augroup slurm_monitor
    autocmd!
    autocmd FocusGained * call s:UpdateSlurmCache()
augroup END
