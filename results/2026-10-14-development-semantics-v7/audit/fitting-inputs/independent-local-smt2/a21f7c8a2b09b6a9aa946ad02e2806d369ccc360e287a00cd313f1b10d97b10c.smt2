(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x76 (bvadd independent_opaque_0 (_ bv2456 32))))
(let ((?x52 (bvadd (bvadd independent_opaque_0 (_ bv2047 32)) (_ bv409 32))))
(and (distinct ?x52 ?x76) true))))
(check-sat)
