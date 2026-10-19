(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x329 (bvadd independent_opaque_0 (_ bv2452 32))))
(let ((?x72 (bvadd (bvadd independent_opaque_0 (_ bv2047 32)) (_ bv405 32))))
(and (distinct ?x72 ?x329) true))))
(check-sat)
