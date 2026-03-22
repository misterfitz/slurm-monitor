" Test that the vim plugin loads correctly.
" Run: vim -u NONE -S tests/test_vim_load.vim

source plugin/slurm.vim

" Verify SlurmStatus function exists
if !exists('*SlurmStatus')
    echom 'FAIL: SlurmStatus function not defined'
    cquit 1
endif

" Verify it returns a string
let result = SlurmStatus()
if type(result) != v:t_string
    echom 'FAIL: SlurmStatus did not return a string'
    cquit 1
endif

" Verify g:loaded_slurm_monitor guard is set
if !exists('g:loaded_slurm_monitor')
    echom 'FAIL: g:loaded_slurm_monitor not set'
    cquit 1
endif

echom 'PASS: vim plugin loaded successfully'
qall!
