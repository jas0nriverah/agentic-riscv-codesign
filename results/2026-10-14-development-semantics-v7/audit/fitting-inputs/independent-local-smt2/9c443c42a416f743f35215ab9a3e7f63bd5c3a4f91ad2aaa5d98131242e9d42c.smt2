(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(assert
 (let ((?x231 (bvadd (_ bv0 32) (_ bv24 32))))
(and (distinct (_ bv24 32) ?x231) true)))
(check-sat)
