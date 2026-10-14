(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x812 (bvshl independent_opaque_1 (bvand (_ bv1 32) (_ bv31 32)))))
(let ((?x1159 (bvadd independent_opaque_0 ?x812)))
(let ((?x10 (bvadd ?x812 independent_opaque_0)))
(and (distinct ?x10 ?x1159) true)))))
(check-sat)
