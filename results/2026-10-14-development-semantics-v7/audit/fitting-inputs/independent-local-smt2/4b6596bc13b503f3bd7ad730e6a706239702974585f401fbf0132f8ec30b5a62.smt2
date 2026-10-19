(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x7 (bvadd independent_opaque_0 (bvadd independent_opaque_1 (_ bv4294966908 32)))))
(let ((?x17 (bvadd (bvadd independent_opaque_0 (_ bv4294966908 32)) independent_opaque_1)))
(and (distinct ?x17 ?x7) true))))
(check-sat)
