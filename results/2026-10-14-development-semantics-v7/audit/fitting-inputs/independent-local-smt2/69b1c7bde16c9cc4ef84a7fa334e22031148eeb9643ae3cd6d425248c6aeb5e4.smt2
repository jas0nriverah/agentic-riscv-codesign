(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x57 (bvadd independent_opaque_0 (bvadd independent_opaque_1 (_ bv4294966272 32)))))
(and (distinct ?x57 ?x57) true)))
(check-sat)
