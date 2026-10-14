(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x98 (bvshl independent_opaque_1 (bvand (_ bv4 32) (_ bv31 32)))))
(let ((?x126 (bvadd independent_opaque_0 ?x98)))
(let ((?x625 (bvadd ?x98 independent_opaque_0)))
(and (distinct ?x625 ?x126) true)))))
(check-sat)
