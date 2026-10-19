(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x85 (bvshl independent_opaque_1 (bvand (_ bv24 32) (_ bv31 32)))))
(let ((?x1183 (bvadd independent_opaque_0 ?x85)))
(let ((?x33 (bvadd ?x85 independent_opaque_0)))
(and (distinct ?x33 ?x1183) true)))))
(check-sat)
