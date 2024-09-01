.text
.global _start
_start:
    /* calculate pointer to envp array */
    ldr r0, [sp]
    add r0, #2
    lsl r0, #2
    add r0, sp

    /* store pointer to envp array */
    ldr r1, =envp
    str r0, [r1]

    /* setuid(0) */
    mov r0, #0          /* uid = 0 (root) */
    mov r7, #23         /* syscall number for setuid */
    svc #0              /* make the syscall */

    /* setgid(0) */
    mov r0, #0          /* gid = 0 (root) */
    mov r7, #46         /* syscall number for setgid */
    svc #0              /* make the syscall */

    /* execve("/system/bin/sh", ["/system/bin/sh"], envp) */
    ldr r0, =filename   /* pointer to filename */
    ldr r1, =argv       /* pointer to argv array */
    ldr r2, =envp
    ldr r2, [r2]        /* pointer to envp array */
    mov r7, #11         /* syscall number for execve */
    svc #0              /* make the syscall */

    /* exit with execve return code, only reached if execve fails */
    mov r7, #1          /* syscall number for exit */
    svc #0              /* make the syscall */

.data
filename:
    .asciz "/system/bin/sh"
argv:
    .word filename      /* argv[0] = filename */
    .word 0             /* argv[1] = NULL */

.bss
envp:
    .word
