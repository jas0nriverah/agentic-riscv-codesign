(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x43 (bvadd independent_opaque_0 (bvadd independent_opaque_1 (_ bv160 32)))))
(let ((?x35 (bvadd (bvadd independent_opaque_0 (_ bv160 32)) independent_opaque_1)))
(and (distinct ?x35 ?x43) true))))
(check-sat)
