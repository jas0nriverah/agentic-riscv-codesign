(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x329 (bvadd independent_opaque_0 (_ bv7 32))))
(let ((?x446 (bvadd (bvadd independent_opaque_0 (_ bv8 32)) (_ bv4294967295 32))))
(and (distinct ?x446 ?x329) true))))
(check-sat)
