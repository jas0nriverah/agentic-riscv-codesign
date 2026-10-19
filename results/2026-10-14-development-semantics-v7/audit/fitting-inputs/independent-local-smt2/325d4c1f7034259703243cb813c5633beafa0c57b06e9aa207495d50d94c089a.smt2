(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x255 (bvshl independent_opaque_0 (bvand (_ bv26 32) (_ bv31 32)))))
(let ((?x289 (bvadd ?x255 independent_opaque_1)))
(let ((?x1180 (bvadd independent_opaque_1 ?x255)))
(and (distinct ?x1180 ?x289) true)))))
(check-sat)
