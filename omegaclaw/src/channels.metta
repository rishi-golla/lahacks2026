; OmegaClaw channel wiring for MetaGlasses backend.
; Mirrors Tutorial 04 integration points:
;   - initChannels
;   - receive
;   - send

(= (MY_BACKEND_URL) (empty))
(= (MY_BACKEND_SECRET) (empty))
(= (MY_BACKEND_POLL_MS) (empty))

(= (initChannels)
   (progn
      (println! "Initializing channels")
      (if (== (commchannel) my_backend)
         (py-call
            (my_backend.start_my_backend
               (MY_BACKEND_URL)
               (MY_BACKEND_SECRET)
               (MY_BACKEND_POLL_MS))))))

(= (receive)
   (if (== (commchannel) my_backend)
      (py-call (my_backend.getLastMessage))
      (empty)))

(= (send $msg)
   (if (== (commchannel) my_backend)
      (py-call (my_backend.send_message $msg))
      (empty)))
